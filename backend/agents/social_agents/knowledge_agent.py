import json
import os
import logging
import random
from llm_client import call_llm
from datetime import datetime
from utils.logger_util import setup_rotating_logger

class KnowledgeAgent:
    def __init__(self, llm_provider: str = None, llm_model: str = None, config_path: str = None, is_enabled: bool = True):
        # Setup per-agent logger and reset log file on init (treat init as reset)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        log_dir = os.path.join(backend_dir, "logs")
        self._log_file = os.path.join(log_dir, "knowledge_agent.log")
        os.makedirs(log_dir, exist_ok=True)
        # Truncate and write reset header
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== KnowledgeAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("knowledge_agent", self._log_file, force=True)

        # Load defaults from JSON config
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "knowledge_agent.json")

        cfg = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            self.logger.warning(
                "KnowledgeAgent config not found at %s; prompts must be provided via JSON."
                , config_path
            )
        except Exception as e:
            self.logger.exception("Failed to read KnowledgeAgent config: %s", e)

        # Provider/model from config, allow explicit overrides via constructor
        self.llm_provider = llm_provider if llm_provider is not None else cfg.get("llm_provider", "test")
        self.llm_model = llm_model if llm_model is not None else cfg.get("llm_model", "test")

        # Template strings; must be provided via JSON config
        self.system_prompt_template = cfg.get("system_prompt_template")
        self.user_prompt_template = cfg.get("user_prompt_template")

        if not self.system_prompt_template:
            raise ValueError("Missing 'system_prompt_template' in knowledge_agent.json")
        if not self.user_prompt_template:
            raise ValueError("Missing 'user_prompt_template' in knowledge_agent.json")
        
        # Enable/disable flag
        self.is_enabled = is_enabled
        
    def analyze_knowledge(
        self, 
        name, personality, knowledge,
        dialogue: str, 
    ) -> dict:
        """
        Analyzes dialogue to extract and update knowledge base.

        Args:
            dialogue (str): Current conversation text
            knowledge_json (dict, optional): Existing knowledge base
            llm (any, optional): LLM interface object

        Returns:
            dict: Updated knowledge base with new entries

        Raises:
            ValueError: If LLM is not provided
        """
        # Helper to safely format templates that include literal JSON braces
        def _safe_format(template: str, mapping: dict, placeholders: list[str]) -> str:
            # First, replace placeholders with temporary tokens
            token_map = {ph: f"__PH_{i}__" for i, ph in enumerate(placeholders)}
            tmp = template
            
            # Replace placeholder braces with temporary tokens
            for ph, token in token_map.items():
                tmp = tmp.replace("{" + ph + "}", token)
            
            # Escape remaining braces (for JSON literals)
            tmp = tmp.replace("{", "{{").replace("}", "}}")
            
            # Restore placeholder braces
            for ph, token in token_map.items():
                tmp = tmp.replace(token, "{" + ph + "}")
            
            # Now format with actual values
            return tmp.format(**mapping)

        # Build prompts by formatting templates with provided parameters
        knowledge_json = json.dumps(knowledge or {}, ensure_ascii=False)
        system_prompt = _safe_format(
            self.system_prompt_template,
            {
                "name": name,
                "personality": personality,
                "knowledge": knowledge_json,
            },
            ["name", "personality", "knowledge"],
        )
        user_prompt = _safe_format(
            self.user_prompt_template,
            {
                "name": name,
                "personality": personality,
                "knowledge": knowledge_json,
                "dialogue": dialogue
            },
            ["name", "personality", "knowledge", "dialogue"],
        )

        response_text = None

        if not self.is_enabled:
            return {}
            
        if self.llm_provider == "test":
            # Return contextually relevant test response based on actual dialogue content
            import re
            
            # Extract character names from dialogue (speakers only)
            people_mentioned = []
            dialogue_lines = dialogue.split('\n')
            for line in dialogue_lines:
                # Look for "Name:" pattern at start of line (speakers)
                name_match = re.match(r'^([A-Za-z]+):\s*', line)
                if name_match:
                    speaker = name_match.group(1)
                    if speaker not in people_mentioned and speaker not in ['Day', 'Participants']:
                        people_mentioned.append(speaker)
            
            # Extract location from dialogue context
            places_mentioned = []
            location_match = re.search(r'@\s*([^|]+)', dialogue)
            if location_match:
                location = location_match.group(1).strip()
                places_mentioned.append(location)
            
            # Extract objects/items mentioned (look for specific nouns)
            objects_mentioned = []
            # Common objects that might appear in fantasy dialogues
            object_patterns = ['piano', 'hearth', 'strings', 'bell', 'ink', 'thread', 'wings', 'hexagram', 'book', 'sword', 'staff', 'crystal', 'mirror', 'candle', 'scroll']
            dialogue_lower = dialogue.lower()
            for obj in object_patterns:
                if re.search(r'\b' + obj + r'\b', dialogue_lower):
                    if obj not in objects_mentioned:
                        objects_mentioned.append(obj)
            
            # Create events based on dialogue structure
            events = []
            if places_mentioned:
                events.append(f"Conversation at {places_mentioned[0]}")
            if len(people_mentioned) >= 2:
                events.append(f"Dialogue between {' and '.join(people_mentioned)}")
            
            # Create contextually relevant response
            test_response = {
                "entities": {
                    "people": people_mentioned,
                    "places": places_mentioned,
                    "objects": objects_mentioned[:5],  # Limit to first 5
                    "events": events
                },
                "relationships": [],
                "timeline": []
            }
            
            response_text = json.dumps(test_response, ensure_ascii=False)
        elif self.llm_provider:
            # Delegate to centralized LLM client for real providers
            response_text = call_llm(
                self.llm_provider,
                self.llm_model,
                system_prompt,
                user_prompt,
                temperature=0.2,
                agent_name="knowledge_agent",
            )
        else:
            # No provider specified and test not selected
            raise ValueError("No llm_provider specified. Use 'test' or a supported provider (e.g., 'openrouter'). The old 'active_llm' concept is removed.")

        self.logger.info(
            "KNOWLEDGE AGENT\nSystem:%s\nUser:%s\nResponse:%s",
            system_prompt,
            user_prompt,
            response_text,
        )

        # Try to parse JSON; if not, wrap into a minimal structure
        updated_knowledge: dict
        try:
            updated_knowledge = json.loads(response_text)
            if not isinstance(updated_knowledge, dict):
                updated_knowledge = {"raw": response_text}
        except Exception:
            updated_knowledge = {"raw": response_text}

        return updated_knowledge

    def set_is_enabled(self, is_enabled: bool):
        self.is_enabled = is_enabled
    
    def set_llm_provider(self, llm_provider="test", llm_model="test"):
        self.llm_provider = llm_provider
        self.llm_model = llm_model
    
    def get_llm_provider(self):
        return self.llm_provider, self.llm_model
        
    def set_user_prompt(self, user_prompt: str):
        # Accept a template string with {dialogue} placeholder
        self.user_prompt_template = user_prompt
    
    def set_system_prompt(self, system_prompt: str):
        # Accept a template string with {name}, {personality}, {knowledge} placeholders
        self.system_prompt_template = system_prompt

    def reset_log(self) -> None:
        """Reset (truncate) this agent's log file and reconfigure the rotating logger."""
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== KnowledgeAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("knowledge_agent", self._log_file, force=True)
