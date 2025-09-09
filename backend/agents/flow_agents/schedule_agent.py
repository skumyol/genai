import logging
import os
from collections import defaultdict
from typing import List, Optional, Tuple
from output_parser import output_parser_list
from utils.logger_util import setup_rotating_logger
import json

class ScheduleAgent:
    def __init__(self, llm_provider: Optional[str] = None, llm_model: Optional[str] = None, fallback_models: Optional[List[Tuple[str, str]]] = None):
        # History keyed by day -> phase -> list of pairs
        self.schedule_history = defaultdict(dict)
        # LLM configuration
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        # Optional list of fallback models passed to llm_client.call_llm
        self.fallback_models: Optional[List[Tuple[str, str]]] = fallback_models

        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        print("schedule_agent log_dir: ", log_dir)
        os.makedirs(log_dir, exist_ok=True)

        # Initialize logger
        self.logger = setup_rotating_logger(
            "schedule_agent", os.path.join(log_dir, "schedule_agent.log"), force=True
        )
        self.logger.info("ScheduleAgent initialized")  # Test logging

    # LLM configuration accessors
    def set_llm_provider(self, provider: str):
        self.llm_provider = provider

    def get_llm_provider(self) -> Optional[str]:
        return self.llm_provider

    def set_llm_model(self, model: str):
        self.llm_model = model

    def get_llm_model(self) -> Optional[str]:
        return self.llm_model

    def get_schedule(self, phase: str):
        """Return scheduled (initiator, recipient) pairs for the given phase."""
        try:
            return self.schedule_today_by_phase.get(phase, [])
        except Exception:
            return []

    def _already_spoken_names(self, day: int, phase: str, npc_name: str):
        """Compute names this NPC has already been paired with today for the given phase using history and today's schedule."""
        names = set()
        try:
            # From history for the same day/phase
            day_sched = self.schedule_history.get(day, {}) or {}
            pairs = list((day_sched or {}).get(phase, []))
            # Also include current in-memory schedule for this phase
            pairs += list((getattr(self, 'schedule_today_by_phase', {}) or {}).get(phase, []))
            for a, b in pairs:
                if a == npc_name and b:
                    names.add(b)
                elif b == npc_name and a:
                    names.add(a)
        except Exception:
            pass
        return list(names)

    def set_schedule(
        self,
        active_npcs_from_lifecycle_agent,
        memory_agent,
        day: int,
        phases: list[str],
    ):
        """
        Build and return the schedule grouped by phase.

        Args:
            memory_agent (MemoryAgent): The memory agent
            active_character_names (list): List of active character names
            day (int): Current day
            phases (list): List of phases in the day

        Returns:
            dict: {
                'by_phase': { phase: [(initiator, recipient), ...], ... }
            }
        """
        # Local schedule (do not mutate instance state)
        schedule_by_phase = {phase: set() for phase in phases}

        # Validate names against all NPC names in memory (supports single NPC_Agent usage)
        all_npc_names = set(memory_agent.get_all_npc_names() or [])

        if not all_npc_names:
            self.logger.warning("No valid NPC names provided. Created empty phase schedules.")
            return {"by_phase": {p: [] for p in phases}}

        for phase in phases:
            # Choose active characters for this phase (explicitly pass llm=None)
            # Ensure validity
            for name in active_npcs_from_lifecycle_agent:
                schedule = self.schedule_character(name, active_npcs_from_lifecycle_agent, day, phase, memory_agent)

                # Filter invalid or self
                schedule = [r for r in schedule if (r in all_npc_names) and (r != name)]

                for recipient in schedule:
                    if (recipient, name) not in schedule_by_phase[phase] and (name, recipient) not in schedule_by_phase[phase]:
                        schedule_by_phase[phase].add((name, recipient))

        # Convert sets to lists for serialization
        schedule_by_phase_list = {phase: list(pairs) for phase, pairs in schedule_by_phase.items()}
        # Persist schedule for retrieval during phases and history by day
        self.schedule_today_by_phase = schedule_by_phase_list
        try:
            # Save a copy in history keyed by day
            self.schedule_history[day] = schedule_by_phase_list
        except Exception:
            pass
        return schedule_by_phase_list

    def schedule_character(
        self, npc_name, active_character_names, day, phase, memory_agent
    ):  # phase is the current phase of the day like morning, noon, afternoon, etc.
        self.logger.info(f"Day {day}, {phase}: Scheduling character: {npc_name}")
        prompt = self.prompt_schedule(
            npc_name, active_character_names, day, phase, memory_agent
        )

        try:
            # Use configured provider/model via llm_client with explicit system/user
            from llm_client import call_llm
            # Extract system and user from prompt
            if isinstance(prompt, dict):
                if 'system' in prompt and 'user' in prompt:
                    system_msg = prompt.get('system', "")
                    user_msg = prompt.get('user', "")
                elif 'messages' in prompt:
                    msgs = prompt.get('messages')
                    if isinstance(msgs, list):
                        system_msg = next((mm.get('content', '') for mm in msgs if isinstance(mm, dict) and mm.get('role') == 'system'), "")
                        user_msg = next((mm.get('content', '') for mm in msgs if isinstance(mm, dict) and mm.get('role') == 'user'), "")
                    else:
                        system_msg = f"You schedule conversations for {npc_name}."
                        user_msg = str(prompt)
                else:
                    # Fallback parsing
                    system_msg = f"You schedule conversations for {npc_name}."
                    user_msg = str(prompt)
            else:
                # Fallback parsing
                system_msg = f"You schedule conversations for {npc_name}."
                user_msg = str(prompt)

            import os
            provider = self.llm_provider or os.environ.get("LLM_PROVIDER") or "openrouter"
            model = self.llm_model or os.environ.get("LLM_MODEL")
            if not model:
                raise ValueError("ScheduleAgent llm_model is not configured (LLM_MODEL env or constructor)")
            self.logger.info(f"--- Start Schedule Agent: Schedule NPC ({npc_name}) ---")
            self.logger.info(f"Day {day}, {phase}: System Prompt: {system_msg}")
            self.logger.info(f"Day {day}, {phase}: User Prompt: {user_msg}")
            response = call_llm(
                provider,
                model,
                system_msg,
                user_msg,
                temperature=0.2,
                fallback_models=self.fallback_models,
                agent_name="schedule_agent",
            )
            self.logger.info(f"Day {day}, {phase}: LLM Response: {response}")
            self.logger.info(f"--- End Schedule Agent: Schedule NPC ({npc_name}) ---")

        except Exception as e:
            self.logger.exception(f"Day {day}, {phase}: Error calling LLM for {npc_name} schedule: {e}")
            # Fallback: select one random character to talk to
            available_chars = [name for name in active_character_names if name != npc_name]
            response = available_chars[0] if available_chars else ""

        try:
            response_list = output_parser_list.parse(response)
            # Filter out the character themselves and invalid names
            response_list = [name for name in response_list if name != npc_name and name in active_character_names]
            self.logger.info(f"Day {day}, {phase}: {npc_name} schedule result: {response_list}")
        except Exception as e:
            self.logger.error(f"Day {day}, {phase}: Error parsing schedule response for {npc_name}: {e}")
            response_list = []

        return response_list

    def prompt_schedule(
        self, npc_name, active_character_names, day, phase, memory_agent
    ):
        # Harmonized prompt style (matching lifecycle_agent)
        system = f"""
        You are the 'Scheduler' for a medieval fantasy world, a silent observer who decides which characters will cross paths. Your task is to create a compelling social schedule for {npc_name} during the {phase} of day {day}.
        """.strip()
        # Compute already-spoken names from schedule history to avoid duplicates
        already_spoken = self._already_spoken_names(day, phase, npc_name)

        # Safely retrieve optional dialogue summary from memory_agent (correct accessor)
        try:
            summary_text = ""
            if memory_agent and hasattr(memory_agent, 'get_npc_dialogue_summary'):
                summary_text = memory_agent.get_npc_dialogue_summary(npc_name) or "No memories yet."
        except Exception:
            summary_text = "Could not retrieve memories."

        # Get opinions using the new opinion functions
        opinions_text = "{}"
        try:
            if memory_agent and hasattr(memory_agent, 'get_npc_all_opinions'):
                outgoing = memory_agent.get_npc_all_opinions(npc_name) or {}
                # Build incoming opinions map: what others think about this npc
                incoming = {}
                try:
                    all_names = memory_agent.get_all_npc_names() or []
                except Exception:
                    all_names = []
                for other in all_names:
                    if other == npc_name:
                        continue
                    try:
                        op = memory_agent.get_npc_opinion(other, npc_name)
                        if op:
                            incoming[other] = op
                    except Exception:
                        continue
                opinions_text = json.dumps({"outgoing": outgoing, "incoming": incoming})
        except Exception:
            # Use instance logger to avoid NameError
            self.logger.error(f"Failed to retrieve opinions for {npc_name}")
            opinions_text = "{}"

        user = f"""
        ### CHARACTER TO SCHEDULE
        - **Name:** {npc_name}

        ### CONTEXT FOR YOUR DECISION
        - **Time:** Day {day}, {phase}
        - **Available Characters for Interaction:** {active_character_names}
        - **Characters Already Spoken To Today:** {already_spoken}
        - **{npc_name}'s Memory Summary:** {summary_text}
        - **Web of Opinions (What they think of others, and others of them):** {opinions_text}

        ### YOUR TASK
        Based on the context, decide who {npc_name} should interact with in this phase. A good schedule creates drama, resolves tension, or develops relationships.

        ### INSTRUCTIONS
        1.  Choose characters from the 'Available Characters' list.
        2.  Do not schedule {npc_name} to talk to themselves.
        3.  Prioritize characters they haven't spoken to today.
        4.  Your output must be a single line of comma-separated names (CSV).
        5.  If no interaction is logical, return an empty line.

        ### EXAMPLE
        `Elara, Grak`

        ### SCHEDULE FOR {npc_name} (CSV ONLY):
        """.strip()
        return {"system": system, "user": user}
