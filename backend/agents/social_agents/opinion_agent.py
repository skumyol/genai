import json
import os
import logging
import random
from typing import Union
from llm_client import call_llm
from datetime import datetime
from utils.logger_util import setup_rotating_logger


class OpinionAgent:
    def __init__(self, llm_provider: str = None, llm_model: str = None, config_path: str = None, is_enabled: bool = True):
        # Setup per-agent logger and reset log file on init (treat init as reset)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        log_dir = os.path.join(backend_dir, "logs")
        self._log_file = os.path.join(log_dir, "opinion_agent.log")
        os.makedirs(log_dir, exist_ok=True)
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== OpinionAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("opinion_agent", self._log_file, force=True)

        # Load defaults from JSON config
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "opinion_agent.json")

        cfg = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            self.logger.warning(
                "OpinionAgent config not found at %s; prompts must be provided via JSON.",
                config_path,
            )
        except Exception as e:
            self.logger.exception("Failed to read OpinionAgent config: %s", e)

        # Provider/model from config, allow explicit overrides via constructor
        self.llm_provider = llm_provider if llm_provider is not None else cfg.get("llm_provider", "test")
        self.llm_model = llm_model if llm_model is not None else cfg.get("llm_model", "test")

        # Template strings; must be provided via JSON config
        self.system_prompt_template = cfg.get("system_prompt_template")
        self.user_prompt_template = cfg.get("user_prompt_template")

        if not self.system_prompt_template:
            raise ValueError("Missing 'system_prompt_template' in opinion_agent.json")
        if not self.user_prompt_template:
            raise ValueError("Missing 'user_prompt_template' in opinion_agent.json")
        
        # Enable/disable flag
        self.is_enabled = is_enabled

    def _safe_format(self, template: str, mapping: dict, placeholders: list[str]) -> str:
        """Safely format a template that may contain JSON braces."""
        token_map = {ph: f"__PH_{i}__" for i, ph in enumerate(placeholders)}
        tmp = template
        for ph, token in token_map.items():
            tmp = tmp.replace("{" + ph + "}", token)
        tmp = tmp.replace("{", "{{").replace("}", "}}")
        for ph, token in token_map.items():
            tmp = tmp.replace(token, "{" + ph + "}")
        return tmp.format(**mapping)

    def generate_opinion(
        self,
        name: str,
        personality: str,
        story: str,
        recipient: str,
        incoming_message: str,
        recipient_reputation: Union[str, None] = None,
        dialogue: Union[str, None] = None,
    ) -> str:
        """
        Generate an opinion (ideally a single-word summary) about the recipient, from the
        perspective of the agent defined by name/personality/story and their dialogue.
        """
        if not self.is_enabled:
            return "Neutral"
        
        reputation_text = (
            f"Reputation: {recipient_reputation}" if recipient_reputation else ""
        )

        system_prompt = self._safe_format(
            self.system_prompt_template,
            {
                "name": name,
                "personality": personality,
                "story": story,
            },
            ["name", "personality", "story"],
        )

        # Prefer explicit dialogue context if provided; otherwise fall back to incoming_message only
        dialogue_text = dialogue if dialogue else incoming_message
        # Ensure persona fields are present in the user prompt mapping so templates
        # that include the persona block (name/personality/story) are fully filled.
        # Convert non-string personality/story to readable strings (e.g., dict -> JSON)
        try:
            personality_text = personality if isinstance(personality, str) else json.dumps(personality)
        except Exception:
            personality_text = str(personality)
        try:
            story_text = story if isinstance(story, str) else json.dumps(story)
        except Exception:
            story_text = str(story)

        user_prompt = self._safe_format(
            self.user_prompt_template,
            {
                "name": name,
                "personality": personality_text,
                "story": story_text,
                "recipient": recipient,
                "incoming_message": incoming_message,
                "dialogue": dialogue_text,
                "recipient_reputation": reputation_text,
            },
            ["name", "personality", "story", "recipient", "incoming_message", "dialogue", "recipient_reputation"],
        )

        response_text: Union[str, None] = None

        if self.llm_provider == "test":
            # Return random plausible single-word opinions without calling any external LLM
            samples = [
                "trustworthy",
                "suspicious",
                "friendly",
                "hostile",
                "neutral",
            ]
            response_text = random.choice(samples)
        elif self.llm_provider:
            response_text = call_llm(
                self.llm_provider,
                self.llm_model,
                system_prompt,
                user_prompt,
                temperature=0.2,
                agent_name="opinion_agent",
            )
        else:
            raise ValueError(
                "No llm_provider specified. Use 'test' or a supported provider (e.g., 'openrouter'). The old 'active_llm' concept is removed."
            )

        self.logger.info(
            "OPINION AGENT\nSystem:%s\nUser:%s\nResponse:%s",
            system_prompt,
            user_prompt,
            response_text,
        )

        return response_text


    # --- Getters/Setters for LLM and prompts ---
    def reset_log(self) -> None:
        """Reset (truncate) this agent's log file and reconfigure the rotating logger."""
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== OpinionAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("opinion_agent", self._log_file, force=True)

    def set_llm_provider(self, llm_provider: str = "test", llm_model: str = "test") -> None:
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    def get_llm_provider(self) -> tuple[str, str]:
        return self.llm_provider, self.llm_model

    def set_user_prompt(self, user_prompt: str) -> None:
        # Accept a template string with {recipient}, {incoming_message}, {recipient_reputation}
        self.user_prompt_template = user_prompt

    def set_system_prompt(self, system_prompt: str) -> None:
        # Accept a template string with {name}, {personality}, {story}
        self.system_prompt_template = system_prompt

    def set_is_enabled(self, is_enabled: bool):
        self.is_enabled = is_enabled
