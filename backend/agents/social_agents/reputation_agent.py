import json
import os
import logging
import random
from typing import Optional, Union
from llm_client import call_llm
from datetime import datetime
from utils.logger_util import setup_rotating_logger

class ReputationAgent:
    def __init__(self, llm_provider: str = None, llm_model: str = None, config_path: str = None, is_enabled: bool = True):
        # Setup per-agent logger and reset log file on init (treat init as reset)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        log_dir = os.path.join(backend_dir, "logs")
        self._log_file = os.path.join(log_dir, "reputation_agent.log")
        os.makedirs(log_dir, exist_ok=True)
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== ReputationAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("reputation_agent", self._log_file, force=True)

        # Load defaults from JSON config
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "reputation_agent.json")

        cfg = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            self.logger.warning(
                "ReputationAgent config not found at %s; prompts must be provided via JSON.",
                config_path,
            )
        except Exception as e:
            self.logger.exception("Failed to read ReputationAgent config: %s", e)

        # Provider/model from config, allow explicit overrides via constructor
        self.llm_provider = llm_provider if llm_provider is not None else cfg.get("llm_provider", "test")
        self.llm_model = llm_model if llm_model is not None else cfg.get("llm_model", "test")

        # Template strings; must be provided via JSON config
        self.system_prompt_template = cfg.get("system_prompt_template")
        self.user_prompt_template = cfg.get("user_prompt_template")

        if not self.system_prompt_template:
            raise ValueError("Missing 'system_prompt_template' in reputation_agent.json")
        if not self.user_prompt_template:
            raise ValueError("Missing 'user_prompt_template' in reputation_agent.json")

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

    def _format_opinions(self, opinions: Union[dict, list, None]) -> str:
        if not opinions:
            return "(no opinions available)"
        try:
            if isinstance(opinions, dict):
                lines = [f"- {k}: {v}" for k, v in opinions.items()]
                return "\n".join(lines)
            if isinstance(opinions, list):
                # Expect list of tuples or dicts
                parts = []
                for item in opinions:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        parts.append(f"- {item[0]}: {item[1]}")
                    elif isinstance(item, dict):
                        # Try keys 'name' and 'opinion'
                        name = item.get("name") or item.get("npc") or item.get("from") or "unknown"
                        op = item.get("opinion") or item.get("value") or item.get("about") or "unknown"
                        parts.append(f"- {name}: {op}")
                    else:
                        parts.append(f"- {str(item)}")
                return "\n".join(parts) if parts else "(no opinions available)"
        except Exception:
            return str(opinions)

    def generate_reputation(
        self,
        *,
        character_name: str,
        world_definition: str,
        opinions: Union[dict, list, None],
        dialogues: str,
        current_reputation: Optional[str] = None,
    ) -> str:
        """
        Generate a one- or two-word reputation phrase for the character based on
        world definition, opinions, and dialogue history.
        """
        current_rep_text = current_reputation or "neutral"
        if not self.is_enabled:
            return "Neutral"
        
        opinions_block = self._format_opinions(opinions)

        system_prompt = self._safe_format(
            self.system_prompt_template,
            {"world_definition": world_definition or ""},
            ["world_definition"],
        )

        user_prompt = self._safe_format(
            self.user_prompt_template,
            {
                "character_name": character_name,
                "current_reputation": current_rep_text,
                "opinions": opinions_block,
                "dialogues": dialogues or "",
            },
            ["character_name", "current_reputation", "opinions", "dialogues"],
        )

        response_text: Optional[str] = None

        if self.llm_provider == "test":
            samples = [
                "neutral",
                "trusted",
                "loose cannon",
                "scheming",
                "honorable",
                "hot-headed",
                "shrewd",
                "benevolent",
                "cautious",
                "brash",
            ]
            response_text = random.choice(samples)
        elif self.llm_provider:
            response_text = call_llm(
                self.llm_provider,
                self.llm_model,
                system_prompt,
                user_prompt,
                temperature=0.2,
                agent_name="reputation_agent"
            )
        else:
            raise ValueError(
                "No llm_provider specified. Use 'test' or a supported provider (e.g., 'openrouter'). The old 'active_llm' concept is removed."
            )

        # Light post-processing to enforce one or two words only
        cleaned = (response_text or "").strip().splitlines()[0]
        words = cleaned.split()
        if len(words) > 2:
            cleaned = " ".join(words[:2])

        self.logger.info(
            "REPUTATION AGENT\nSystem:%s\nUser:%s\nResponse:%s\nFinal:%s",
            system_prompt,
            user_prompt,
            response_text,
            cleaned,
        )
        return cleaned

    # --- Getters/Setters for LLM and prompts ---
    def set_llm_provider(self, llm_provider: str = "test", llm_model: str = "test") -> None:
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    def get_llm_provider(self) -> tuple[str, str]:
        return self.llm_provider, self.llm_model

    def set_user_prompt(self, user_prompt: str) -> None:
        # Accept a template string with {character_name}, {current_reputation}, {opinions}, {dialogues}
        self.user_prompt_template = user_prompt

    def set_system_prompt(self, system_prompt: str) -> None:
        # Accept a template string with {world_definition}
        self.system_prompt_template = system_prompt

    def reset_log(self) -> None:
        """Reset (truncate) this agent's log file and reconfigure the rotating logger."""
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== ReputationAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("reputation_agent", self._log_file, force=True)

    def set_is_enabled(self, is_enabled: bool):
        self.is_enabled = is_enabled
