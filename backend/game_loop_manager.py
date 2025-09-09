"""
Game Loop Manager - Orchestrates the entire game simulation
"""

import logging
import time
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from threading import Event

from agents.memory_agent import MemoryAgent
from agents.flow_agents.lifecycle_agent import LifeCycleAgent
from agents.flow_agents.schedule_agent import ScheduleAgent
from agents.dialogue_agent import DialogueAgent
from agents.npc_agent import NPC_Agent
from agents.dialogue_handler import DialogueHandler
from agents.social_agents.opinion_agent import OpinionAgent
from agents.social_agents.social_stance_agent import SocialStanceAgent
from agents.social_agents.knowledge_agent import KnowledgeAgent
from agents.social_agents.reputation_agent import ReputationAgent
import llm_client as llm_client
from utils.logger_util import setup_rotating_logger


logger = logging.getLogger(__name__)

class CharacterList:
    """Manages the list of characters in the game"""
    def __init__(self, characters: Dict[str, Any]):
        self.characters = characters
    
    def get_character_names(self) -> List[str]:
        """Get all character names"""
        return list(self.characters.keys())
    
    def get_character(self, name: str) -> Optional[Dict]:
        """Get character by name"""
        return self.characters.get(name)

class GameLoopManager:
    """Main game loop orchestrator"""
    
    def __init__(self, memory_agent: MemoryAgent, sse_manager=None, stop_event: Optional[Event] = None,
                 llm_provider: Optional[str] = None, llm_model: Optional[str] = None,
                 agent_llm_configs: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
                 reputation_enabled: bool = True):
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        self.memory_agent = memory_agent
        self.sse_manager = sse_manager
        self.stop_event: Optional[Event] = stop_event
        # LLM configuration for flow agents (global fallback)
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        # Per-agent LLM configuration mapping. Example keys: 'lifecycle_agent', 'schedule_agent', 'npc_agent', 'dialogue_agent'
        self.agent_llm_configs: Dict[str, Dict[str, Optional[str]]] = agent_llm_configs or {}
        self.reputation_enabled: bool = bool(reputation_enabled)
        
        # Initialize character list from memory agent's NPCs
        self.character_list = self._init_character_list()
        
        # Initialize agents with per-agent LLM configs (fallback to global if unspecified)
        logger.info("Initializing LifeCycleAgent")
        lc_cfg = (self.agent_llm_configs.get('lifecycle_agent') or
                  {"provider": self.llm_provider, "model": self.llm_model})
        lc_kwargs = {}
        if lc_cfg.get("provider") is not None:
            lc_kwargs["llm_provider"] = lc_cfg.get("provider")
        if lc_cfg.get("model") is not None:
            lc_kwargs["llm_model"] = lc_cfg.get("model")
        
        # Process fallbacks if they exist in config
        fallback_list = lc_cfg.get("fallback_models")
        if fallback_list and isinstance(fallback_list, list):
            fallbacks = []
            for fb in fallback_list:
                if isinstance(fb, dict):
                    prov = fb.get("provider")
                    mod = fb.get("model")
                    if prov and mod:
                        fallbacks.append((prov, mod))
            if fallbacks:
                lc_kwargs["fallback_models"] = fallbacks
                logger.info(f"LifeCycleAgent fallbacks: {fallbacks}")
                
        if lc_kwargs:
            logger.info(f"LifeCycleAgent LLM: {lc_kwargs.get('llm_provider')}/{lc_kwargs.get('llm_model')}")
        else:
            logger.info("LifeCycleAgent LLM: using agent defaults")
        self.lifecycle_agent = LifeCycleAgent(
            **lc_kwargs,
        )
        
        logger.info("Initializing ScheduleAgent")
        
        sch_cfg = (self.agent_llm_configs.get('schedule_agent') or
                   {"provider": self.llm_provider, "model": self.llm_model})
        sch_kwargs = {}
        if sch_cfg.get("provider") is not None:
            sch_kwargs["llm_provider"] = sch_cfg.get("provider")
        if sch_cfg.get("model") is not None:
            sch_kwargs["llm_model"] = sch_cfg.get("model")
        # Process fallbacks if present
        sch_fallback_list = sch_cfg.get("fallback_models")
        if sch_fallback_list and isinstance(sch_fallback_list, list):
            sch_fallbacks = []
            for fb in sch_fallback_list:
                if isinstance(fb, dict):
                    prov = fb.get("provider")
                    mod = fb.get("model")
                    if prov and mod:
                        sch_fallbacks.append((prov, mod))
            if sch_fallbacks:
                sch_kwargs["fallback_models"] = sch_fallbacks
                logger.info(f"ScheduleAgent fallbacks: {sch_fallbacks}")
        if sch_kwargs:
            logger.info(f"ScheduleAgent LLM: {sch_kwargs.get('llm_provider')}/{sch_kwargs.get('llm_model')}")
        else:
            logger.info("ScheduleAgent LLM: using agent defaults")
        self.schedule_agent = ScheduleAgent(
            **sch_kwargs,
        )
        
        # Verify ScheduleAgent logger
        if hasattr(self.schedule_agent, 'logger'):
            self.schedule_agent.logger.info("ScheduleAgent initialized successfully")
            logger.info(f"ScheduleAgent logger handlers: {self.schedule_agent.logger.handlers}")
        else:
            logger.error("ScheduleAgent has no logger attribute")
        
        # Initialize single stateless NPC agent (use 'npc_agent' if present, otherwise allow 'dialogue_agent' as alias)
        npc_cfg = (self.agent_llm_configs.get('npc_agent') or
                   self.agent_llm_configs.get('dialogue_agent') or
                   {"provider": self.llm_provider, "model": self.llm_model})
        npc_provider = npc_cfg.get("provider")
        npc_model = npc_cfg.get("model")
        if npc_provider is not None or npc_model is not None:
            # Fill missing values from global/env defaults to satisfy types
            safe_npc_provider = npc_provider or self.llm_provider or os.environ.get("LLM_PROVIDER") or "openrouter"
            safe_npc_model = npc_model or self.llm_model or os.environ.get("LLM_MODEL") or "test"
            logger.info(f"NPC_Agent LLM: {safe_npc_provider}/{safe_npc_model}")
            self.npc_agent = NPC_Agent(self.memory_agent, llm_provider=safe_npc_provider, llm_model=safe_npc_model)
        else:
            logger.info("NPC_Agent LLM: using agent defaults")
            self.npc_agent = NPC_Agent(self.memory_agent)
        
        # Initialize other agents
        self.opinion_agent = OpinionAgent()
        self.social_stance_agent = SocialStanceAgent()
        self.knowledge_agent = KnowledgeAgent()
        self.reputation_agent = ReputationAgent()
        # Configure ReputationAgent LLM if provided
        rep_cfg = (self.agent_llm_configs.get('reputation_agent') or {})
        rep_provider = rep_cfg.get("provider") or self.llm_provider
        rep_model = rep_cfg.get("model") or self.llm_model
        if rep_provider or rep_model:
            try:
                safe_rep_provider = rep_provider or os.environ.get("LLM_PROVIDER") or "openrouter"
                safe_rep_model = rep_model or os.environ.get("LLM_MODEL") or "test"
                self.reputation_agent.set_llm_provider(safe_rep_provider, safe_rep_model)
                logger.info(f"ReputationAgent LLM: {safe_rep_provider}/{safe_rep_model}")
            except Exception:
                pass
        
        # Initialize dialogue handler
        self.dialogue_handler = DialogueHandler(
            npc_agent=self.npc_agent,
            memory_agent=self.memory_agent,
            opinion_agent=self.opinion_agent,
            social_stance_agent=self.social_stance_agent,
            knowledge_agent=self.knowledge_agent,
            reputation_agent=self.reputation_agent,
            sse_manager=self.sse_manager,
            max_messages_per_dialogue=10,
            max_tokens_per_dialogue=2000,
            goodbye_threshold=2,
            reputation_enabled=self.reputation_enabled,
        )
        
        # Game state
        self.current_day = 1
        # Phases from default settings
        world = self.memory_agent.get_world() or {}
        raw_periods = ((world.get("calendar") or {}).get("time_periods") or [])
        # Normalize to uppercase for storage but keep a display string
        self.phases = [str(p) for p in raw_periods] or ["MORNING", "NOON", "AFTERNOON", "EVENING", "NIGHT"]
        self.current_phase = self.phases[0]
        self.active_dialogues = {}
        self.active_characters = []
        self.passive_characters = []
        # Holds schedules returned by ScheduleAgent for the current day
        self._day_schedule = {}
    
    def _should_stop(self) -> bool:
        """Return True if an external stop signal was issued."""
        return bool(self.stop_event and self.stop_event.is_set())
        
    def _init_character_list(self) -> CharacterList:
        """Initialize character list from MemoryAgent's game_settings character_list"""
        characters: Dict[str, Any] = {}
        for c in self.memory_agent.get_character_list():
            name = c.get("name")
            if not name:
                continue
            char_data = {
                "name": name,
                "story": c.get("story", ""),
                "personality": c.get("personality", {}),
                "location_home": c.get("location_home", (c.get("locations", {}) or {}).get("home")),
                "location_work": c.get("location_work", (c.get("locations", {}) or {}).get("work")),
                "role": c.get("role", ""),
                "type": c.get("type", "npc"),
                "life_cycle": c.get("life_cycle", "active"),
            }
            characters[name] = char_data
        return CharacterList(characters)
    
    def _init_dialogue_handler(self):
        """Initialize dialogue handler with the stateless NPC agent"""
        # This is now handled in __init__
        pass
    async def run_day_cycle(self):
        """Runs a complete day cycle with simplified logic and error handling."""
        sid = getattr(getattr(self.memory_agent, 'current_session', None), 'session_id', None)
        logger.info(f"Session {sid} — Starting Day {self.current_day} Cycle")
        if self._should_stop():
            return

        await self._broadcast_event("day_start", {"day": self.current_day, "phase": "morning"})

        # 1. Lifecycle Agent: Determine active/passive characters and introduce new ones
        logger.info(f"Session {sid} Day {self.current_day}: Calling LifeCycle Agent")

        self.active_characters, self.passive_characters = self.lifecycle_agent.update_life_cycle_map(self.memory_agent, self.active_characters, self.passive_characters)
        new_character = self.lifecycle_agent.introduce_new_characters(self.memory_agent, self.active_characters)
        # 2. Persist New Characters: If a new character was introduced, add them to the memory
        if new_character:
            logger.info(f"Session {sid} Day {self.current_day}: New character introduced: {new_character.get('name')}")
            try:
                self.memory_agent.add_character(new_character)
                # Re-initialize character list to include the new character
                self.character_list = self._init_character_list()
            except Exception as e:
                logger.exception(f"Failed to add new character to session: {e}")

        # Note: Day data is created per phase in run_phase; avoid duplicate creation here
        # 4. Schedule Agent: Create the schedule for the entire day
        logger.info(f"Session {sid} Day {self.current_day}: Calling Schedule Agent for the full day")

        schedule = self.schedule_agent.set_schedule(
            self.active_characters,self.memory_agent, self.current_day, self.phases,
        )
        # Ensure a safe default structure

        self._day_schedule = schedule
        

        # 5. Run Phases: Execute each phase of the day
        total_phases = len(self.phases)
        for phase_idx, phase in enumerate(self.phases, 1):
            if self._should_stop():
                logger.info(f"Day {self.current_day}: Stopping at phase {phase} ({phase_idx}/{total_phases})")
                break
            await self.run_phase(phase, self.active_characters)

        # 6. End of Day: Perform cleanup and advance to the next day
        if not self._should_stop():
            await self.end_of_day_processing()
            self.current_day += 1

        
    async def run_phase(self, phase: str, active_characters: List[str]):
        """Runs a single phase of the day."""
        sid = getattr(getattr(self.memory_agent, 'current_session', None), 'session_id', None)
        logger.info(f"Session {sid} Day {self.current_day}: === Starting Phase: {phase} ===")
        if self._should_stop():
            return

        await self._broadcast_event("phase_start", {"day": self.current_day, "phase": phase})

        # 1. Set NPC locations for the current phase
        for name in self.character_list.get_character_names():
            self.npc_agent.set_location_by_time(name, phase)

        # 2. Persist DayData for the current phase
        all_names = self.memory_agent.get_all_npc_names()
        passive_names = [n for n in all_names if n not in active_characters]
        self.memory_agent.create_day(self.current_day, self._to_time_period(phase), active_characters, passive_names)
        
        # Ensure session time reflects the current day and phase for accurate dialogue timestamps
        self.memory_agent.advance_time(new_day=self.current_day, new_time_period=self._to_time_period(phase).value)

        # 3. Get scheduled conversations for this phase
        scheduled_conversations = self.schedule_agent.get_schedule(phase)
        logger.info(f"Session {sid} Day {self.current_day}, {phase}: Retrieved {len(scheduled_conversations)} scheduled conversations: {list(scheduled_conversations)}")

        # 4. Execute conversations
        conversation_count = 0
        for initiator, recipient in scheduled_conversations: # one conversation pair at a time
            if self._should_stop(): #listen for the frontent interrupt
                logger.info(f"Session {sid} Day {self.current_day}, {phase}: Stopping conversation execution at {conversation_count}/{len(scheduled_conversations)}")
                break
            await self.run_conversation(initiator, recipient, phase)
            conversation_count += 1

        logger.info(f"Session {sid} Day {self.current_day}, {phase}: Completed {conversation_count}/{len(scheduled_conversations)} conversations")

            
    async def run_conversation(self, initiator: str, recipient: str, phase: str):
        """Run a conversation between two NPCs using the dialogue handler"""
        sid = getattr(getattr(self.memory_agent, 'current_session', None), 'session_id', None)
        logger.info(f"Session {sid} Day {self.current_day}, {phase}: === Starting Conversation: {initiator} -> {recipient} ===")
        if self._should_stop():
            return
        
        # Ensure there is an active session
        current_session = self.memory_agent.current_session
        if not current_session:
            logger.error("No active session found")
            return
        # Validate NPC names exist in character list to prevent runtime errors
        if not self.character_list.get_character(initiator) or not self.character_list.get_character(recipient):
            logger.warning(f"Session {sid} Day {self.current_day}, {phase}: Invalid conversation pair {initiator}->{recipient}; skipping")
            return
        
        try:
            # Execute the dialogue using the dialogue handler
            # Design requirement: do not skip dialogues due to location.
            # If locations differ, proceed anyway and let the dialogue occur.

            dialogue = await self.dialogue_handler.execute_scheduled_dialogue(
                initiator_name=initiator,
                responder_name=recipient,
                location=self.npc_agent.get_current_location(recipient) or self.memory_agent.get_location(recipient),
                phase=phase,
            )
            
            logger.info(f"Session {sid} Day {self.current_day}, {phase}: Dialogue completed between {initiator} and {recipient}")
            
        except Exception as e:
            logger.error(f"Session {sid} Day {self.current_day}, {phase}: Error in conversation between {initiator} and {recipient}: {e}")
        
    async def end_of_day_processing(self):
        """Process end of day tasks"""
        sid = getattr(getattr(self.memory_agent, 'current_session', None), 'session_id', None)
        logger.info(f"Session {sid} End of day {self.current_day} processing")
        
        # Get all active NPC names
        active_npc_names = []
        for char_id, char_data in self.character_list.characters.items():
            if char_data.get('life_cycle') == 'active':
                active_npc_names.append(char_id)
        
        # Reset ephemeral per-partner conversation contexts at end of day
        try:
            await self.dialogue_handler.clear_daily_conversation_contexts(active_npc_names)
        except Exception as e:
            logger.warning(f"Failed to clear daily conversation contexts: {e}")
            
        # Broadcast day end
        await self._broadcast_event("day_end", {
            "day": self.current_day,
            "next_day": self.current_day + 1
        })
        
    async def _generate_conversation_summary(self, dialogue) -> Optional[str]:
        """Summarize a completed dialogue via LLM, similar to MemoryAgent summarization."""
        try:
            if not dialogue or not getattr(dialogue, 'dialogue_id', None):
                return None
            # Fetch messages for the dialogue
            import asyncio as _asyncio
            msgs = await _asyncio.to_thread(self.memory_agent.get_dialogue_messages, dialogue.dialogue_id)
            if not msgs:
                return None
            # Build content
            lines = []
            for m in msgs:
                try:
                    speaker = getattr(m, 'sender', '') or ''
                    text = (getattr(m, 'message_text', '') or '').replace('\n', ' ').strip()
                    if text:
                        lines.append(f"{speaker}: {text}")
                except Exception:
                    continue
            if not lines:
                return None
            dialogue_text = "\n".join(lines)

            # Prompts (aligned with MemoryAgent style)
            system_prompt = (
                "You are a game dialogue summarizer. Create a concise yet comprehensive summary "
                "of the conversation, preserving key facts, relationships, goals, and unresolved threads. "
                "Output plain text only."
            )
            max_chars = int(os.environ.get("DIALOGUE_SUMMARY_MAX_CHARS", "800"))
            user_prompt = (
                "Dialogue:\n" + dialogue_text + "\n\n" +
                f"Write a unified summary under ~{max_chars} characters. Prefer specifics; avoid fluff."
            )

            # Provider/model: prefer configured top-level, fall back to defaults
            provider = self.llm_provider or os.environ.get("LLM_PROVIDER") or "openrouter"
            model = self.llm_model or os.environ.get("LLM_MODEL")
            if not model:
                # Fallback to truncated text if no model configured
                return dialogue_text[:max_chars]

            # Run LLM in thread to avoid blocking loop
            summary = await _asyncio.to_thread(
                llm_client.call_llm,
                provider,
                model,
                system_prompt,
                user_prompt,
                temperature=0.2,
                fallback_models=None,
            )
            if isinstance(summary, str):
                return summary.strip()
            return None
        except Exception as e:
            logger.warning(f"Dialogue summary generation failed: {e}")
            return None
    
    async def _broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event via SSE, scoped to the current session."""
        # SSE broadcasting disabled - frontend handles events directly
        pass
    
    async def _broadcast_active_characters(self):
        """Broadcast active characters via SSE, scoped to the current session."""
        # SSE broadcasting disabled - frontend handles characters directly
        pass
    
    async def _broadcast_message(self, conversation_id: str, sender: str,
                                 recipient: str, text: str):
        """Broadcast a message via SSE, scoped to the current session."""
        # SSE broadcasting disabled - frontend handles messages directly
        pass
    
    async def _async_sleep(self, seconds: float):
        """Async sleep helper"""
        # In a real async environment, use asyncio.sleep.
        # Here we sleep in small increments to allow stop checks.
        remaining = max(0.0, float(seconds))
        interval = 0.1
        while remaining > 0:
            if self._should_stop():
                break
            step = interval if remaining > interval else remaining
            time.sleep(step)
            remaining -= step

    def _to_time_period(self, period: str):
        """Helper to convert raw period string to TimePeriod enum used in dataclasses"""
        from agents.dataclasses import TimePeriod
        p = (period or "").lower()
        # TimePeriod enum uses lowercase values like 'morning'
        return TimePeriod(p)
