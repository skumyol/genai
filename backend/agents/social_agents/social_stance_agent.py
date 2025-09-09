import json
import os
import logging
from llm_client import call_llm
from datetime import datetime
from utils.logger_util import setup_rotating_logger

class SocialStanceAgent:
    def __init__(self, llm_provider: str = None, llm_model: str = None, config_path: str = None, is_enabled: bool = True):
        # Setup per-agent logger and reset log file on init (treat init as reset)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        log_dir = os.path.join(backend_dir, "logs")
        self._log_file = os.path.join(log_dir, "social_stance_agent.log")
        os.makedirs(log_dir, exist_ok=True)
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== SocialStanceAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("social_stance_agent", self._log_file, force=True)
        # Load defaults from JSON config
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "social_stance_agent.json")

        cfg = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            self.logger.warning(
                "SocialStanceAgent config not found at %s; prompts must be provided via JSON.",
                config_path,
            )
        except Exception as e:
            self.logger.exception("Failed to read SocialStanceAgent config: %s", e)

        # Provider/model from config, allow explicit overrides via constructor
        self.llm_provider = llm_provider if llm_provider is not None else cfg.get("llm_provider", "test")
        self.llm_model = llm_model if llm_model is not None else cfg.get("llm_model", "test")

        # Template strings; must be provided via JSON config
        self.system_prompt_template = cfg.get("system_prompt_template")
        self.user_prompt_template = cfg.get("user_prompt_template")

        if not self.system_prompt_template:
            raise ValueError("Missing 'system_prompt_template' in social_stance_agent.json")
        if not self.user_prompt_template:
            raise ValueError("Missing 'user_prompt_template' in social_stance_agent.json")
        
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

    def set_social_stance(self, npc_name, npc_personality, opponent_name, opponent_reputation, opponent_opinion, knowledge_base, dialogue_memory, interaction_history):
        """Generates social interaction stance based on knowledge and reputation."""
        
        # Count interactions from dialogue memory if it's a list
        interaction_count = len(dialogue_memory) if isinstance(dialogue_memory, dict) and opponent_name in dialogue_memory else 0
        reputation_weight = 1.0 / (1.0 + (0.1 * interaction_count))  # Decreases with more interactions
        knowledge_weight = 1.0 - reputation_weight

        self.logger.info("interaction_count: %s, interaction_history %s, reputation_weight: %s, knowledge_weight: %s", interaction_count, interaction_history, reputation_weight, knowledge_weight)
        self.logger.info("knowledge_base: %s", knowledge_base)

        # Prepare formatted strings for prompts
        system_prompt = self._safe_format(
            self.system_prompt_template,
            {
                "npc_name": npc_name,
                "npc_personality": npc_personality,
                "opponent_name": opponent_name,
                "interaction_history": interaction_history,
                "reputation_weight": f"{reputation_weight:.2f}",
                "knowledge_weight": f"{knowledge_weight:.2f}",
                "opponent_reputation": opponent_reputation,
                "opponent_opinion": opponent_opinion,
                "knowledge_base": json.dumps(knowledge_base, ensure_ascii=False),
            },
            [
                "npc_name",
                "npc_personality",
                "opponent_name",
                "interaction_history",
                "reputation_weight",
                "knowledge_weight",
                "opponent_reputation",
                "opponent_opinion",
                "knowledge_base",
            ],
        )

        user_prompt = self._safe_format(
            self.user_prompt_template,
            {
                "reputation_weight_pct": f"{reputation_weight * 100:.0f}",
                "knowledge_weight_pct": f"{knowledge_weight * 100:.0f}",
            },
            ["reputation_weight_pct", "knowledge_weight_pct"],
        )
        if not self.is_enabled:
            return "Neutral"
        response = call_llm(self.llm_provider, self.llm_model, system_prompt, user_prompt, temperature=0.2, agent_name="social_stance_agent")
        return response

    # --- Getters/Setters ---
    def set_llm_provider(self, llm_provider: str = "test", llm_model: str = "test") -> None:
        self.llm_provider = llm_provider
        self.llm_model = llm_model

    def get_llm_provider(self) -> tuple[str, str]:
        return self.llm_provider, self.llm_model

    def set_system_prompt(self, system_prompt: str) -> None:
        self.system_prompt_template = system_prompt

    def set_user_prompt(self, user_prompt: str) -> None:
        self.user_prompt_template = user_prompt

    def get_system_prompt(self) -> str:
        return self.system_prompt_template

    def get_user_prompt(self) -> str:
        return self.user_prompt_template

    def reset_log(self) -> None:
        """Reset (truncate) this agent's log file and reconfigure the rotating logger."""
        with open(self._log_file, "w", encoding="utf-8") as f:
            f.write(f"=== SocialStanceAgent reset at {datetime.utcnow().isoformat()}Z ===\n")
        self.logger = setup_rotating_logger("social_stance_agent", self._log_file, force=True)

    def set_is_enabled(self, is_enabled: bool):
        self.is_enabled = is_enabled
