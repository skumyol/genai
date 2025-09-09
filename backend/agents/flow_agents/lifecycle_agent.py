"""Agent that manages the life cycle of characters at the start of a day."""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple
from output_parser import output_parser_list, output_parser_json
from llm_client import call_llm
from utils.logger_util import setup_rotating_logger

logger = logging.getLogger(__name__)

class LifeCycleAgent:
    def __init__(self, llm_provider: str = "", llm_model: str = "", fallback_models: Optional[List[Tuple[str, str]]] = None):
        self.life_cycle_map = {}
        self.life_cycle_map_history = []
        # LLM configuration
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        # Optional list of fallback models passed to llm_client.call_llm
        self.fallback_models: Optional[List[Tuple[str, str]]] = fallback_models
        
        # Get absolute path to logs directory
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        self.logger = setup_rotating_logger(
            "lifecycle_agent", 
            str(log_dir / "lifecycle_agent.log"),
            force=True  # Ensure file handler is always created
        )

    # LLM configuration accessors
    def set_llm_provider(self, provider: str):
        self.llm_provider = provider

    def get_llm_provider(self) -> str:
        return self.llm_provider

    def set_llm_model(self, model: str):
        self.llm_model = model

    def get_llm_model(self) -> str:
        return self.llm_model

    def decide_life_cycles(self, memory_agent, previous_active=None, previous_passive=None):
        # Build user prompt inline (merged from prompt_life_cycle)
        get_acc_mem = getattr(memory_agent, "get_accumulative_dialogue_memory", None)
        if callable(get_acc_mem):
            global_memory_dialogues = get_acc_mem()
        else:
            global_memory_dialogues = "no conversations yet, this is the beginning of the new game"

        all_names = memory_agent.get_all_npc_names()
        prev_active_str = ", ".join(previous_active or [])
        prev_passive_str = ", ".join(previous_passive or [])
        # Build prompts cleanly
        system = """
        You are the 'Director' of a story, deciding which characters step into the spotlight for the next scene. Your goal is to create a dynamic and engaging narrative.
        """.strip()

        user = f"""
        ### STORY CONTEXT
        - **Recent Events (Global Dialogue History):**
        ---
        {global_memory_dialogues}
        ---
        - **The Cast (All Characters):** {all_names}
        - **Last Scene's Active Characters:** [{prev_active_str}]
        - **Last Scene's Off-stage Characters:** [{prev_passive_str}]

        ### YOUR TASK
        Based on the recent events, decide which characters should be **active** in the next scene to drive the story forward.

        ### INSTRUCTIONS
        - Consider who was central to the last scene and who has been quiet for too long.
        - A good scene has a mix of characters, not everyone needs to be active at once.
        - Your output must be a single line of comma-separated names (CSV).
        - Example: `Elara, Grak, Anya`

        ### ACTIVE CHARACTERS FOR NEXT SCENE:
        """.strip()
        # Use configured provider/model or default to OpenRouter + Llama
        import os
        provider = self.llm_provider or os.environ.get("LLM_PROVIDER") or "openrouter"
        model = self.llm_model or os.environ.get("LLM_MODEL")
        if not model:
            raise ValueError("LifecycleAgent llm_model is not configured (LLM_MODEL env or constructor)")
        self.logger.info(f"--- Start LifeCycle Agent: Active/Passive List ---")
        self.logger.info(f"System Prompt: {system}")
        self.logger.info(f"User Prompt: {user}")
        response = call_llm(
            provider,
            model,
            system,
            user,
            temperature=0.5,
            fallback_models=self.fallback_models,
            agent_name="lifecycle_agent",
        )
        self.logger.info(f"LLM Response: {response}")
        self.logger.info(f"--- End LifeCycle Agent: Active/Passive List ---")
        
        # Create a list of valid character names for validation
        valid_character_names = memory_agent.get_all_npc_names()
        
        try:
            # First try to parse as comma-separated list
            response_clean = response.split("\n\n")[-1].strip()  # Get the last part (after explanations)
            raw_list = output_parser_list.parse(response_clean)
            
            # Validate character names - only include names that are in the valid list
            response_list = [name for name in raw_list if name in valid_character_names]
            
            # If no valid names were found, use the existing list
            if not response_list:
                logging.warning(f"No valid character names found in LLM response: {response}. Using existing active characters.")
                response_list = list(valid_character_names)
        except Exception as e:
            # Fallback if parsing fails
            logging.error(f"Error parsing LLM response: {e}. Response: {response}")
            logging.warning("Using all characters as fallback active list.")
            response_list = list(valid_character_names)
            
        return response_list

    def update_life_cycle_map(self, memory_agent, previous_active=None, previous_passive=None):
        active_character_list = self.decide_life_cycles(memory_agent, previous_active, previous_passive)
        new_life_cycle_map = {}
        
        # Validate each character in active_character_list
        valid_character_names = memory_agent.get_all_npc_names()
        
        for character in active_character_list:
            if character in valid_character_names:
                new_life_cycle_map[character] = "active"
                
        # Ensure we have at least some active characters
        if not new_life_cycle_map:
            logging.warning("No valid active characters found. Using default characters.")
            # Use the first few valid characters as a fallback
            for character in valid_character_names[:2]:  # Use at least 2 characters
                new_life_cycle_map[character] = "active"
                
        # Add remaining valid characters as passive
        for character in valid_character_names:
            if character not in new_life_cycle_map:
                new_life_cycle_map[character] = "passive"
                
        self.life_cycle_map = new_life_cycle_map
        # Add to history
        self.life_cycle_map_history.append(new_life_cycle_map)
        active_names = [n for n, v in new_life_cycle_map.items() if v == "active"]
        passive_names = [n for n, v in new_life_cycle_map.items() if v == "passive"]
        logging.info(f"new_life_cycle_map: {new_life_cycle_map}")
        logging.info(f"active_characters: {active_names}")
        logging.info(f"passive_characters: {passive_names}")
        return active_names, passive_names

    def get_life_cycle_map(self):
        return self.life_cycle_map

    def introduce_new_characters(self, memory_agent, active_characters):  # uses accumulative memory
        if len(memory_agent.get_all_npc_names()) >= 10:
            return None

        # Build system prompt inline (merged)
        system = """
        You are the 'Storyteller' of a medieval fantasy world, deciding if a new character should enter the narrative. Your goal is to enrich the story by introducing new personalities and plot hooks at the right moment.
        """.strip()
        world_desc_fn = getattr(memory_agent, "get_world_description", None)
        world_desc = world_desc_fn() if callable(world_desc_fn) else ""
        if world_desc:
            system += f"\n**World Setting:** {world_desc}"

        # Build user prompt inline (merged)
        character_limit = 10
        get_acc_mem = getattr(memory_agent, "get_accumulative_dialogue_memory", None)
        if callable(get_acc_mem):
            global_memory_dialogues = get_acc_mem()
        else:
            global_memory_dialogues = "The story has just begun."

        all_names = memory_agent.get_all_npc_names()
        game_settings = getattr(memory_agent, "current_session", None)
        roles = []
        locations = []
        if game_settings and getattr(game_settings, "game_settings", None):
            gs = game_settings.game_settings
            roles = gs.get("roles", []) or []
            locations = gs.get("locations", []) or []

        user = f"""
        ### STORY SO FAR
        - **Recent Events:**
        ---
        {global_memory_dialogues}
        ---
        - **Current Cast:** {all_names} (Total: {len(all_names)}/{character_limit})
        - **Currently Active Characters:** {active_characters}

        ### POTENTIAL NEW CHARACTER ARCHETYPES
        - **Roles:** {roles}
        - **Locations:** {locations}

        ### YOUR TASK
        Analyze the story and decide if introducing a new character would make it more interesting.

        ### INSTRUCTIONS
        1.  **Evaluate the Need:** Is the story becoming stale? Is a new role or perspective needed? Only introduce a character if they add significant value.
        2.  **Character Limit:** Do not introduce a new character if the cast has 7 or more members. The hard limit is {character_limit}.
        3.  **Create a Character:** If you decide to add a character, create a compelling profile. Ensure they are distinct from the existing cast.
        4.  **Output Format:**
            - If introducing a character, provide a **JSON object** with `name`, `story`, `personality`, `role`, `location_home`, and `location_work`.
            - If not, return an **empty JSON object** `{{}}`.
        5.  **Your output must be ONLY the JSON object.**

        ### EXAMPLE of a new character JSON:
        ```json
        {{
          "name": "Kaelen",
          "story": "A disgraced knight seeking redemption.",
          "personality": "Brooding and honorable.",
          "role": "Blacksmith",
          "location_home": "The Old Forge",
          "location_work": "The Town Square"
        }}
        ```

        ### DECISION (JSON ONLY):
        """.strip()

        # Use configured provider/model with sensible defaults
        provider = self.llm_provider or os.environ.get("LLM_PROVIDER") or "openrouter"
        model = self.llm_model or os.environ.get("LLM_MODEL")
        if not model:
            raise ValueError("LifecycleAgent llm_model is not configured (LLM_MODEL env or constructor)")
        self.logger.info(f"--- Start LifeCycle Agent: Introduce New Character ---")
        self.logger.info(f"System Prompt: {system}")
        self.logger.info(f"User Prompt: {user}")
        response = call_llm(
            provider,
            model,
            system,
            user,
            temperature=0.5,
            fallback_models=self.fallback_models,
            agent_name="lifecycle_agent",
        )
        self.logger.info(f"LLM Response: {response}")
        self.logger.info(f"--- End LifeCycle Agent: Introduce New Character ---")
        response_json = output_parser_json.parse(response)
        logger.info(f"introduce_new_characters response: {response_json}")
        if len(response_json) == 6:
            response_json["life_cycle"] = "active"
            return response_json
        else:
            return None

    def get_active_characters(self):
        return [n for n, v in self.life_cycle_map.items() if v == "active"]

    def get_passive_characters(self):
        return [n for n, v in self.life_cycle_map.items() if v == "passive"]
