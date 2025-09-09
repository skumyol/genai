"""
Memory Agent for Text-Based Game
Acts as a wrapper/listener that uses DatabaseManager for all database operations
Handles memory management, conversation tracking, and provides high-level game operations
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from logging import getLogger
from database_manager import DatabaseManager
from agents.dataclasses import (
    MainGameData, SessionData, DayData, Dialogue, Message, NPCMemory, TimePeriod
)
from llm_client import call_llm

logger = getLogger(__name__)


class MemoryAgent:
    """Memory agent that acts as a wrapper/listener using DatabaseManager for all operations"""
    
    def __init__(self, db_path: str = None, max_context_length: Optional[int] = None):
        """Initialize memory agent with database manager"""
        self.db_manager = DatabaseManager(db_path)
        # Determine summarization threshold from LLM context size when available
        if max_context_length is not None:
            self.max_context_length = max_context_length
        else:
            try:
                # Prefer explicit token window if provided
                tokens = int(os.environ.get("LLM_CONTEXT_WINDOW_TOKENS", "0"))
            except Exception:
                tokens = 0
            # Approximate chars per token; use conservative margin
            approx_chars_per_token = float(os.environ.get("AVG_CHARS_PER_TOKEN", "4"))
            if tokens > 0:
                self.max_context_length = int(tokens * approx_chars_per_token * 0.8)
            else:
                # Fallback default
                self.max_context_length = 4000
        self.current_session: Optional[SessionData] = None
        self.active_dialogues: Dict[str, Dialogue] = {}
        # Track NPCs currently being summarized to avoid duplicate work
        self._summarizing_npcs = set()
        # Track session summarization status
        self._summarizing_session = False
        # Storage lock for background summarization to avoid races with active dialogue updates
        self._storage_lock = threading.Lock()
        
        # Event listeners for simultaneous operations (db + server)
        self.event_listeners: List[callable] = []
    
    def add_event_listener(self, listener: callable):
        """Add event listener for simultaneous operations"""
        self.event_listeners.append(listener)
    
    def remove_event_listener(self, listener: callable):
        """Remove a previously added event listener if present"""
        try:
            self.event_listeners.remove(listener)
        except ValueError:
            pass

    def set_memory_summary_llm(self, provider: Optional[str] = None, model: Optional[str] = None) -> None:
        """Configure LLM for background memory summarization (overrides env)."""
        self._summary_provider = provider
        self._summary_model = model
    
    def _notify_listeners(self, event_type: str, data: Dict[str, Any]):
        """Notify all listeners of an event"""
        for listener in self.event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                print(f"Event listener error: {e}")
    
    def seed_neutral_opinions(self) -> None:
        """Seed default 'Neutral' opinions among all NPC pairs for the current session.
        Only creates opinions that don't already exist.
        """
        if not self.current_session:
            return
        try:
            names = self.get_all_npc_names() or []
        except Exception:
            names = []
        if not names:
            return
        for a in names:
            for b in names:
                if not a or not b or a == b:
                    continue
                try:
                    existing = self.get_npc_opinion(a, b)
                    if not existing:
                        self.update_npc_opinion(a, b, "Neutral")
                except Exception:
                    continue
    
    # ============================================================================
    # Session Management
    # ============================================================================
    
    def create_session(self, session_id: Optional[str] = None, 
                      game_settings: Dict[str, Any] = None,
                      agent_settings: Dict[str, Any] = None) -> SessionData:
        """Create a new game session, loading from default_settings.json if none provided."""
        if game_settings is None:
            try:
                with open('default_settings.json', 'r') as f:
                    game_settings = json.load(f)
                logger.info("Loaded game settings from default_settings.json")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Could not load default_settings.json: {e}")
                game_settings = {}

        session = self.db_manager.create_session(session_id, game_settings, agent_settings)
        self.current_session = session
        try:
            logger.info(
                "Session created: %s | day=%s period=%s",
                session.session_id,
                getattr(session, 'current_day', None),
                getattr(getattr(session, 'current_time_period', None), 'value', None)
            )
        except Exception:
            logger.info(f"Session created: {session.session_id}")

        # Notify listeners (for server updates, etc.)
        self._notify_listeners('session_created', {
            'session_id': session.session_id,
            'session_data': session.to_dict()
        })
        
        # Seed baseline neutral opinions for all NPC pairs
        try:
            self.seed_neutral_opinions()
        except Exception:
            pass

        return session
    
    def load_session(self, session_id: str) -> Optional[SessionData]:
        """Load an existing session"""
        session = self.db_manager.get_session(session_id)
        if session:
            self.current_session = session
            try:
                logger.info(
                    "Session loaded: %s | day=%s period=%s",
                    session.session_id,
                    getattr(session, 'current_day', None),
                    getattr(getattr(session, 'current_time_period', None), 'value', None)
                )
            except Exception:
                logger.info(f"Session loaded: {session.session_id}")
            
            # Notify listeners
            self._notify_listeners('session_loaded', {
                'session_id': session.session_id,
                'session_data': session.to_dict()
            })
            # Ensure character_list includes all NPCs present in DB (checkpoints, etc.)
            try:
                self.get_character_list()
            except Exception:
                pass
        
        return session
    
    # ============================================================================
    # Dialogue Management
    # ============================================================================
    
    def start_dialogue(self, initiator: str, receiver: str, location: str) -> Dialogue:
        """Start a new dialogue between NPCs"""
        if not self.current_session:
            raise ValueError("No active session. Create or load a session first.")
        
        dialogue = self.db_manager.create_dialogue(
            session_id=self.current_session.session_id,
            initiator=initiator,
            receiver=receiver,
            location=location,
            day=self.current_session.current_day,
            time_period=self.current_session.current_time_period
        )
        
        self.active_dialogues[dialogue.dialogue_id] = dialogue
        
        # Update session dialogue list
        self.current_session.dialogue_ids.append(dialogue.dialogue_id)
        self.db_manager.update_session(self.current_session)

        # Also link this dialogue to the current Day row (if present, else create it)
        try:
            day_row = self.db_manager.get_day(self.current_session.session_id, self.current_session.current_day)
            if not day_row:
                # Ensure day exists with current time period
                day_row = self.db_manager.create_day(
                    session_id=self.current_session.session_id,
                    day=self.current_session.current_day,
                    time_period=self.current_session.current_time_period,
                    active_npcs=self.current_session.active_npcs or [],
                    passive_npcs=[],
                )
            if dialogue.dialogue_id not in (day_row.dialogue_ids or []):
                day_row.dialogue_ids.append(dialogue.dialogue_id)
            # Keep time period synced with session just in case
            day_row.time_period = self.current_session.current_time_period
            self.db_manager.update_day(day_row)
        except Exception:
            # Non-critical: day linkage is best-effort
            pass
        
        # Notify listeners
        self._notify_listeners('dialogue_started', {
            'dialogue_id': dialogue.dialogue_id,
            'dialogue_data': dialogue.to_dict()
        })
        
        return dialogue
    
    def add_message(self, dialogue_id: str, sender: str, receiver: str, 
                   message_text: str, sender_opinion: Optional[str] = None,
                   receiver_opinion: Optional[str] = None) -> Message:
        """Add a message to a dialogue"""
        # If dialogue isn't tracked in memory_agent.active_dialogues, attempt to load it
        if dialogue_id not in self.active_dialogues:
            try:
                dialogue = self.db_manager.get_dialogue(dialogue_id)
                if dialogue:
                    # add to active dialogues cache so further calls work as expected
                    self.active_dialogues[dialogue_id] = dialogue
                    # ensure session dialogue list contains it
                    if self.current_session and dialogue_id not in self.current_session.dialogue_ids:
                        self.current_session.dialogue_ids.append(dialogue_id)
                        self.db_manager.update_session(self.current_session)
                else:
                    raise ValueError(f"Dialogue {dialogue_id} not found in DB")
            except Exception as e:
                raise ValueError(f"Dialogue {dialogue_id} not found: {e}")
        
        # Create message using database manager
        message = self.db_manager.create_message(
            dialogue_id=dialogue_id,
            sender=sender,
            receiver=receiver,
            message_text=message_text,
            sender_opinion=sender_opinion,
            receiver_opinion=receiver_opinion
        )
        
        # Update dialogue
        dialogue = self.active_dialogues[dialogue_id]
        dialogue.message_ids.append(message.message_id)
        dialogue.total_text_length += len(message_text)
        self.db_manager.update_dialogue(dialogue)
        
        # Update NPC memories
        self._update_npc_memory(sender, dialogue_id, message_text)
        self._update_npc_memory(receiver, dialogue_id, message_text)
        
        # Notify listeners
        self._notify_listeners('message_added', {
            'message_id': message.message_id,
            'dialogue_id': dialogue_id,
            'message_data': message.to_dict()
        })

        # Append a single-line record to the session-level summary for streaming memory
        try:
            if self.current_session:
                # Use dialogue metadata for day/time if available
                try:
                    d = dialogue  # from above active_dialogues lookup
                    day_str = f"Day {getattr(d, 'day', self.current_session.current_day)}"
                    tp = getattr(getattr(d, 'time_period', None), 'value', None) or getattr(self.current_session.current_time_period, 'value', '')
                    stamp = f"[{day_str} {tp}]"
                except Exception:
                    stamp = f"[Day {self.current_session.current_day} {getattr(self.current_session.current_time_period, 'value', '')}]"
                line = f"{stamp} {sender} -> {receiver}: {message_text}"
                self.append_session_summary(line)
                # Also append to the current day summary
                try:
                    self.append_day_summary(self.current_session.current_day, line)
                except Exception:
                    pass
        except Exception:
            # Non-critical if session summary append fails
            pass

        return message
    
    def end_dialogue(self, dialogue_id: str, summary: Optional[str] = None) -> Dialogue:
        """End a dialogue and optionally add a summary"""
        if dialogue_id not in self.active_dialogues:
            raise ValueError(f"Dialogue {dialogue_id} not found")
        
        dialogue = self.active_dialogues[dialogue_id]
        dialogue.ended_at = datetime.now()
        
        if summary:
            dialogue.summary = summary
            dialogue.summary_length = len(summary)
        
        self.db_manager.update_dialogue(dialogue)
        
        # Notify listeners
        self._notify_listeners('dialogue_ended', {
            'dialogue_id': dialogue_id,
            'dialogue_data': dialogue.to_dict()
        })
        
        del self.active_dialogues[dialogue_id]
        return dialogue
    
    # ============================================================================
    # NPC Memory Management
    # ============================================================================
    
    def get_npc_memory(self, npc_name: str, session_id: Optional[str] = None) -> Optional[NPCMemory]:
        """Get the memory entry for an NPC (identified by name)."""
        if not session_id and self.current_session:
            session_id = self.current_session.session_id
        
        mem = self.db_manager.get_npc_memory(npc_name, session_id)
        # Ensure character_properties exist (backfill from settings if missing)
        if mem and not getattr(mem, 'character_properties', None):
            props = self.get_character_properties(npc_name)
            if props:
                mem.character_properties = props
                self.db_manager.create_or_update_npc_memory(mem)
        return mem
    
    def _update_npc_memory(self, npc_name: str, dialogue_id: str, message_text: str):
        """Update NPC memory with new message content"""
        if not self.current_session:
            return
        
        npc_memory = self.get_npc_memory(npc_name)
        
        if not npc_memory:
            # Create new NPC memory
            npc_memory = NPCMemory(
                npc_name=npc_name,
                session_id=self.current_session.session_id
            )
            # Attach base character properties on first creation
            npc_memory.character_properties = self.get_character_properties(npc_name)
        
        # Add dialogue to dialogue list if not already there
        if dialogue_id not in npc_memory.dialogue_ids:
            npc_memory.dialogue_ids.append(dialogue_id)
        
        # Update messages summary
        conversation_text = f"[{datetime.now().strftime('%H:%M')}] {message_text}"
        npc_memory.messages_summary += f"\n{conversation_text}"
        npc_memory.messages_summary_length = len(npc_memory.messages_summary)
        npc_memory.last_updated = datetime.now()
        
        # Check if we need to summarize
        if npc_memory.messages_summary_length > self.max_context_length:
            self._summarize_npc_memory(npc_memory)
        
        # Save to database
        self.db_manager.create_or_update_npc_memory(npc_memory)
        
        # Notify listeners
        self._notify_listeners('npc_memory_updated', {
            'npc_name': npc_name,
            'session_id': self.current_session.session_id,
            'memory_data': npc_memory.to_dict()
        })
    
    def _summarize_npc_memory(self, npc_memory: NPCMemory):
        """Summarize NPC memory when it gets too long via background LLM call"""
        if not npc_memory or not npc_memory.messages_summary:
            return
        npc_name = npc_memory.npc_name
        # Avoid duplicate concurrent summarizations per NPC
        if npc_name in self._summarizing_npcs:
            return
        self._summarizing_npcs.add(npc_name)

        source_text = npc_memory.messages_summary

        # Launch background thread to run LLM summarization and persist results
        threading.Thread(
            target=self._run_llm_summarization,
            args=(npc_name, source_text),
            daemon=True,
        ).start()

    def _run_llm_summarization(self, npc_name: str, source_text: str):
        """Background task: summarize source_text with LLM and persist to DB"""
        try:
            # Provider/model selection with sensible defaults and fallbacks
            provider = getattr(self, "_summary_provider", None) or os.environ.get("MEMORY_SUMMARY_PROVIDER") or os.environ.get("LLM_PROVIDER") or "openrouter"
            model = getattr(self, "_summary_model", None) or os.environ.get("MEMORY_SUMMARY_MODEL") or os.environ.get("LLM_MODEL") or "openai/gpt-5-chat"

            # Build prompts
            max_chars = int(os.environ.get("MEMORY_SUMMARY_MAX_CHARS", "2000"))
            system_prompt = (
                "You are a game memory summarizer. Create a concise yet comprehensive, "
                "chronological summary of an NPC's dialogues that preserves key facts, relationships, "
                "goals, and unresolved threads. Output plain text only."
            )
            user_prompt = (
                "Dialogue Log:\n" + source_text + "\n\n" +
                f"Write an updated unified summary that captures all important information so far. "
                f"Keep it under ~{max_chars} characters, merge duplicates, and prefer specifics over fluff."
            )

            new_summary = call_llm(provider, model, system_prompt, user_prompt, temperature=0.2, agent_name="memory_summarizer")

            # Persist: update both rolling buffer and dedicated dialogue_summary
            npc_memory = self.get_npc_memory(npc_name)
            if npc_memory:
                with self._storage_lock:
                    npc_memory.messages_summary = new_summary or ""
                    npc_memory.messages_summary_length = len(npc_memory.messages_summary)
                    npc_memory.last_summarized = datetime.now()
                    self.db_manager.create_or_update_npc_memory(npc_memory)

                # Also store official dialogue summary field
                try:
                    with self._storage_lock:
                        self.update_npc_dialogue_summary(npc_name, npc_memory.messages_summary)
                except Exception:
                    # Non-fatal
                    pass

                # Notify listeners
                self._notify_listeners('npc_memory_summarized', {
                    'npc_name': npc_name,
                    'summary_length': npc_memory.messages_summary_length,
                })
        except Exception as e:
            logger.error(f"LLM summarization failed for {npc_name}: {e}")
        finally:
            try:
                self._summarizing_npcs.discard(npc_name)
            except Exception:
                pass
    
    def update_npc_opinion(self, npc_name: str, target_npc: str, opinion: str):
        """Update NPC's opinion about another NPC"""
        if not self.current_session:
            return
        
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            npc_memory = NPCMemory(npc_name=npc_name, session_id=self.current_session.session_id)
        
        npc_memory.opinion_on_npcs[target_npc] = opinion
        npc_memory.last_updated = datetime.now()
        
        self.db_manager.create_or_update_npc_memory(npc_memory)
        
        # Notify listeners
        self._notify_listeners('npc_opinion_updated', {
            'npc_name': npc_name,
            'target_npc': target_npc,
            'opinion': opinion
        })
    
    def update_npc_world_knowledge(self, npc_name: str, knowledge: Dict[str, Any]):
        """Update NPC's world knowledge"""
        if not self.current_session:
            return
        
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            npc_memory = NPCMemory(npc_name=npc_name, session_id=self.current_session.session_id)
        
        npc_memory.world_knowledge.update(knowledge)
        npc_memory.last_updated = datetime.now()
        
        self.db_manager.create_or_update_npc_memory(npc_memory)
        
        # Notify listeners
        self._notify_listeners('npc_knowledge_updated', {
            'npc_name': npc_name,
            'knowledge': knowledge
        })
    
    def update_npc_social_stance(self, npc_name: str, stance: Dict[str, Any]):
        """Update NPC's social stance"""
        if not self.current_session:
            return
        
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            npc_memory = NPCMemory(npc_name=npc_name, session_id=self.current_session.session_id)
        
        npc_memory.social_stance.update(stance)
        npc_memory.last_updated = datetime.now()
        
        self.db_manager.create_or_update_npc_memory(npc_memory)
        
        # Notify listeners
        self._notify_listeners('npc_stance_updated', {
            'npc_name': npc_name,
            'stance': stance
        })
    
    # ============================================================================
    # Query Operations
    # ============================================================================
    
    def get_npc_dialogues(self, npc_name: str, session_id: Optional[str] = None,
                         limit: int = 10) -> List[Dialogue]:
        """Get dialogues involving a specific NPC"""
        if not session_id and self.current_session:
            session_id = self.current_session.session_id
        
        return self.db_manager.get_npc_dialogues(npc_name, session_id, limit)
    
    def get_session_dialogues(self, session_id: Optional[str] = None, 
                             day: Optional[int] = None,
                             time_period: Optional[TimePeriod] = None) -> List[Dialogue]:
        """Get dialogues for a session, optionally filtered by day/time"""
        if not session_id and self.current_session:
            session_id = self.current_session.session_id
        
        return self.db_manager.get_dialogues_by_session(session_id, day, time_period)
    
    def get_dialogue_messages(self, dialogue_id: str) -> List[Message]:
        """Get all messages from a dialogue"""
        return self.db_manager.get_messages_by_dialogue(dialogue_id)
    
    def get_active_dialogues(self) -> List[Dict[str, Any]]:
        """Get all currently active dialogues"""
        return [dialogue.to_dict() for dialogue in self.active_dialogues.values()]

    # --------------------------------------------------------------------------
    # NPC properties and location accessors (from default settings)
    # --------------------------------------------------------------------------

    def _find_character_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        chars = self.get_character_list() or []
        for c in chars:
            if c.get('name') == name:
                return c
        return None

    def get_locations(self, npc_name: str) -> Dict[str, Any]:
        """Return the locations object for an NPC from game settings."""
        char = self._find_character_by_name(npc_name)
        if not char:
            return {}
        locs = char.get('locations') or {}
        return locs if isinstance(locs, dict) else {}

    def get_location(self, npc_name: str) -> str:
        """Return the current location for an NPC from game settings."""
        locs = self.get_locations(npc_name)
        return str(locs.get('current') or '')

    def get_character_properties(self, npc_name: str) -> Dict[str, Any]:
        """Return base character properties aligned with default_settings.json."""
        char = self._find_character_by_name(npc_name)
        if not char:
            return {}
        keys = ['role', 'type', 'locations', 'life_cycle', 'story', 'personality']
        return {k: char.get(k) for k in keys if k in char}

    def add_character(self, character_data: Dict[str, Any]):
        """Add a new character to the session's character list"""
        if not self.current_session:
            raise ValueError("No active session. Cannot add a character.")

        # Ensure game_settings and character_list exist
        if self.current_session.game_settings is None:
            self.current_session.game_settings = {}
        if 'character_list' not in self.current_session.game_settings:
            self.current_session.game_settings['character_list'] = []

        # Use name as the canonical identifier
        name = (character_data or {}).get('name')
        if not name:
            raise ValueError("Character must have a 'name' field")
        # Prevent duplicates by name
        existing_names = {c.get('name') for c in self.current_session.game_settings['character_list']}
        if name in existing_names:
            logger.info(f"Character '{name}' already exists. Skipping add.")
            return name
        character_data['name'] = name
        # Ensure required defaults so downstream code recognizes this as an NPC
        character_data.setdefault('type', 'npc')
        character_data.setdefault('life_cycle', 'active')

        # Add the new character to the list
        self.current_session.game_settings['character_list'].append(character_data)

        # Update the session in the database
        self.db_manager.update_session(self.current_session)

        logger.info(f"Added new character: {character_data['name']}")

        # Create an initial NPC memory row so it appears in NPC datasets immediately
        try:
            mem = self.get_npc_memory(name)
        except Exception:
            mem = None
        if not mem:
            try:
                nm = NPCMemory(npc_name=name, session_id=self.current_session.session_id)
                nm.character_properties = self.get_character_properties(name)
                self.db_manager.create_or_update_npc_memory(nm)
            except Exception:
                pass

        # Seed neutral opinions across NPC pairs including this new one
        try:
            self.seed_neutral_opinions()
        except Exception:
            pass

        # Notify listeners
        self._notify_listeners('character_added', {
            'session_id': self.current_session.session_id,
            'character_data': character_data
        })

        return name
    
    # ============================================================================
    # Time Management
    # ============================================================================
    
    def advance_time(self, new_day: Optional[int] = None, 
                    new_time_period: Optional[Any] = None):
        """Advance game time"""
        if not self.current_session:
            raise ValueError("No active session")
        
        if new_day is not None:
            self.current_session.current_day = new_day
        
        if new_time_period is not None:
            try:
                if isinstance(new_time_period, TimePeriod):
                    self.current_session.current_time_period = new_time_period
                else:
                    self.current_session.current_time_period = TimePeriod(str(new_time_period))
            except Exception:
                # leave unchanged if invalid
                pass
        
        self.current_session.last_updated = datetime.now()
        self.db_manager.update_session(self.current_session)
        
        # Notify listeners
        self._notify_listeners('time_advanced', {
            'session_id': self.current_session.session_id,
            'current_day': self.current_session.current_day,
            'current_time_period': self.current_session.current_time_period.value
        })
    
    def create_day(self, day: int, time_period: TimePeriod, 
                   active_npcs: List[str] = None, passive_npcs: List[str] = None) -> DayData:
        """Create a new day entry"""
        if not self.current_session:
            raise ValueError("No active session")
        
        day_data = self.db_manager.create_day(
            session_id=self.current_session.session_id,
            day=day,
            time_period=time_period,
            active_npcs=active_npcs or [],
            passive_npcs=passive_npcs or []
        )
        
        # Keep session.active_npcs aligned with the created day
        self.current_session.active_npcs = active_npcs or []
        self.db_manager.update_session(self.current_session)
        
        # Notify listeners
        self._notify_listeners('day_created', {
            'session_id': day_data.session_id,
            'day': day_data.day,
            'day_data': day_data.to_dict()
        })
        
        return day_data

    def get_day(self, day: int, session_id: Optional[str] = None) -> Optional[DayData]:
        """Fetch a day by (session_id, day)."""
        if not session_id:
            if not self.current_session:
                return None
            session_id = self.current_session.session_id
        return self.db_manager.get_day(session_id, day)

    def update_day_active_passive(self, day: int, 
                                  active_npcs: List[str], 
                                  passive_npcs: List[str]) -> bool:
        """Update a day's active/passive NPC lists"""
        if not self.current_session:
            return False
        dd = self.db_manager.get_day(self.current_session.session_id, day)
        if not dd:
            return False
        dd.active_npcs = active_npcs or []
        dd.passive_npcs = passive_npcs or []
        return self.db_manager.update_day(dd)
    
    # ============================================================================
    # Game Settings Accessors (world and characters)
    # ============================================================================
    
    
    def get_world(self) -> Dict[str, Any]:
        """Return the world object from game settings"""
        if not self.current_session:
            return {}
        return (self.current_session.game_settings or {}).get('world', {})
    
    def get_world_description(self) -> str:
        world = self.get_world()
        return world.get('description', '') if isinstance(world, dict) else ''
    
    def get_character_list(self) -> List[Dict[str, Any]]:
        """Return the session's character list, merging in any NPCs discovered in the DB.

        This ensures checkpoints that contain NPCs beyond default_settings are reflected
        in game_settings so the frontend can render them reliably.
        """
        if not self.current_session:
            return []
        gs = self.current_session.game_settings or {}
        cl = gs.get('character_list')
        if not isinstance(cl, list):
            cl = []

        # Gather existing names
        existing_names = {c.get('name') for c in cl if isinstance(c, dict) and c.get('name')}

        # Discover NPC names from DB (memories preferred, else dialogues)
        try:
            names = []
            with self.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT npc_name FROM npc_memories WHERE session_id = ?", (self.current_session.session_id,))
                names = [r[0] for r in cur.fetchall() if r and r[0]]
            if not names:
                with self.db_manager.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT DISTINCT initiator FROM dialogues WHERE session_id = ?", (self.current_session.session_id,))
                    names_i = [r[0] for r in cur.fetchall() if r and r[0]]
                    cur.execute("SELECT DISTINCT receiver FROM dialogues WHERE session_id = ?", (self.current_session.session_id,))
                    names_r = [r[0] for r in cur.fetchall() if r and r[0]]
                    names = sorted(set(names_i + names_r))
        except Exception:
            names = []

        # Add any missing NPCs to character_list
        changed = False
        for nm in names:
            if not nm or nm in existing_names:
                continue
            entry = {"name": nm, "type": "npc", "life_cycle": "active"}
            # Enrich from character_properties if present in npc_memories
            try:
                mem = self.get_npc_memory(nm)
                if mem and getattr(mem, 'character_properties', None):
                    props = mem.character_properties or {}
                    for k in ("role", "story", "personality", "locations"):
                        if k in props:
                            entry[k] = props[k]
            except Exception:
                pass
            cl.append(entry)
            existing_names.add(nm)
            changed = True

        # Persist changes if we added any
        if changed or gs.get('character_list') is None:
            gs['character_list'] = cl
            self.current_session.game_settings = gs
            try:
                self.db_manager.update_session(self.current_session)
            except Exception:
                pass

        return cl

    
    def get_npc_context(self, npc_name: str, include_recent_dialogues: bool = True) -> str:
        """Get formatted context for an NPC for LLM prompts"""
        if not self.current_session:
            return ""
        
        npc_memory = self.get_npc_memory(npc_name)
        context_parts = []
        
        if npc_memory:
            # Add memory summary
            if npc_memory.messages_summary:
                context_parts.append(f"Recent conversations:\n{npc_memory.messages_summary}")
            
            # Add opinions
            if npc_memory.opinion_on_npcs:
                opinions = []
                for target, opinion in npc_memory.opinion_on_npcs.items():
                    opinions.append(f"- {target}: {opinion}")
                context_parts.append(f"Opinions on others:\n" + "\n".join(opinions))
            
            # Add world knowledge
            if npc_memory.world_knowledge:
                context_parts.append(f"World knowledge: {npc_memory.world_knowledge}")
            
            # Add social stance
            if npc_memory.social_stance:
                context_parts.append(f"Social stance: {npc_memory.social_stance}")
        
        # Add recent dialogues if requested
        if include_recent_dialogues:
            recent_dialogues = self.get_npc_dialogues(npc_name, limit=3)
            if recent_dialogues:
                dialogue_summaries = []
                for dialogue in recent_dialogues:
                    if dialogue.summary:
                        dialogue_summaries.append(f"- {dialogue.summary}")
                if dialogue_summaries:
                    context_parts.append("Recent dialogue summaries:\n" + "\n".join(dialogue_summaries))
        
        return "\n\n".join(context_parts) if context_parts else f"No context available for {npc_name}"

    # ============================================================================
    # NPC Data Management (for NPC Agent support)
    # ============================================================================
    
    def get_npc_opinion(self, npc_name: str, target_npc: str) -> str:
        """Get NPC's opinion about another NPC"""
        npc_memory = self.get_npc_memory(npc_name)
        if npc_memory and target_npc in npc_memory.opinion_on_npcs:
            return npc_memory.opinion_on_npcs[target_npc]
        return ""
    
    def get_npc_all_opinions(self, npc_name: str) -> Dict[str, str]:
        """Get all opinions of an NPC"""
        npc_memory = self.get_npc_memory(npc_name)
        return npc_memory.opinion_on_npcs if npc_memory else {}
    
    def get_npc_social_stance(self, npc_name: str) -> Dict[str, Any]:
        """Get NPC's social stance"""
        npc_memory = self.get_npc_memory(npc_name)
        return npc_memory.social_stance if npc_memory else {}
    
    def get_npc_world_knowledge(self, npc_name: str) -> Dict[str, Any]:
        """Get NPC's world knowledge"""
        npc_memory = self.get_npc_memory(npc_name)
        return npc_memory.world_knowledge if npc_memory else {}
    
    def get_npc_conversation_history(self, npc_name: str, target_npc: str = None) -> str:
        """Get NPC's conversation history, optionally filtered by target NPC"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            return ""
        
        if target_npc:
            # Filter conversations with specific NPC by name (names are identifiers)
            dialogues = self.get_npc_dialogues(npc_name, limit=50)
            filtered_history = []

            def _participant_matches_target(target: str, a_name: str, b_name: str) -> bool:
                return target == a_name or target == b_name

            for dialogue in dialogues:
                if _participant_matches_target(target_npc, dialogue.initiator, dialogue.receiver):
                    messages = self.get_dialogue_messages(dialogue.dialogue_id)
                    for message in messages:
                        if message.sender == npc_name or message.receiver == npc_name:
                            filtered_history.append(f"[Day {dialogue.day}] {message.sender}: {message.message_text}")
            return "\n".join(filtered_history)
        
        return npc_memory.messages_summary
    
    def get_npc_known_characters(self, npc_name: str) -> List[str]:
        """Get list of characters this NPC has interacted with"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            return []
        
        # Start with names from opinion list (already names by design)
        known_names = set(npc_memory.opinion_on_npcs.keys())

        # Also include participants from dialogues (dialogue stores names as participants)
        dialogues = self.get_npc_dialogues(npc_name, limit=100)
        for dialogue in dialogues:
            if dialogue.initiator != npc_name:
                known_names.add(dialogue.initiator)
            if dialogue.receiver != npc_name:
                known_names.add(dialogue.receiver)

        return list(known_names)
    
    def update_npc_conversation_context(self, npc_name: str, target_npc: str, context: str):
        """Update NPC's conversation context with another NPC"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            npc_memory = NPCMemory(npc_name=npc_name, session_id=self.current_session.session_id)
        
        # Store in world knowledge under conversation contexts
        if 'conversation_contexts' not in npc_memory.world_knowledge:
            npc_memory.world_knowledge['conversation_contexts'] = {}
        
        npc_memory.world_knowledge['conversation_contexts'][target_npc] = context
        npc_memory.last_updated = datetime.now()
        
        self.db_manager.create_or_update_npc_memory(npc_memory)
        
        # Notify listeners
        self._notify_listeners('npc_context_updated', {
            'npc_name': npc_name,
            'target_npc': target_npc,
            'context': context
        })
    
    def get_npc_conversation_context(self, npc_name: str, target_npc: str) -> str:
        """Get NPC's conversation context with another NPC"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            return ""
        
        contexts = npc_memory.world_knowledge.get('conversation_contexts', {})
        return contexts.get(target_npc, "")
    
    def clear_npc_conversation_context(self, npc_name: str):
        """Clear NPC's daily conversation context"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            return
        
        if 'conversation_contexts' in npc_memory.world_knowledge:
            npc_memory.world_knowledge['conversation_contexts'] = {}
            npc_memory.last_updated = datetime.now()
            self.db_manager.create_or_update_npc_memory(npc_memory)
    
    def get_npc_dialogue_summary(self, npc_name: str) -> str:
        """Get NPC's dialogue memory summary"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            return ""
        
        # Return summary from world knowledge if available, otherwise messages summary
        return npc_memory.world_knowledge.get('dialogue_summary', npc_memory.messages_summary)
    
    def update_npc_dialogue_summary(self, npc_name: str, summary: str):
        """Update NPC's dialogue memory summary"""
        npc_memory = self.get_npc_memory(npc_name)
        if not npc_memory:
            npc_memory = NPCMemory(npc_name=npc_name, session_id=self.current_session.session_id)
        
        npc_memory.world_knowledge['dialogue_summary'] = summary
        npc_memory.last_updated = datetime.now()
        
        self.db_manager.create_or_update_npc_memory(npc_memory)
    
    def get_accumulative_dialogue_memory(self) -> str:
        """Get global memory summary for all dialogues in the current session"""
        if not self.current_session:
            return "no conversations yet, this is the beginning of the new game"
        
        return self.current_session.session_summary or "no conversations yet, this is the beginning of the new game"

    # ============================================================================
    # Session (Game) Memory Management
    # ============================================================================
    def append_session_summary(self, text: str) -> None:
        """Append text to the session-level summary and summarize in background if needed."""
        if not self.current_session or not text:
            return
        # Append and persist
        sep = "\n" if self.current_session.session_summary else ""
        self.current_session.session_summary = (self.current_session.session_summary or "") + sep + text
        self.db_manager.update_session(self.current_session)

        # Trigger background summarization if length exceeds threshold
        try:
            if len(self.current_session.session_summary) > self.max_context_length:
                self._summarize_session_memory()
        except Exception:
            pass

    def _summarize_session_memory(self) -> None:
        if not self.current_session or not self.current_session.session_summary:
            return
        if self._summarizing_session:
            return
        self._summarizing_session = True
        source_text = self.current_session.session_summary
        threading.Thread(
            target=self._run_session_summarization,
            args=(source_text,),
            daemon=True,
        ).start()

    def _run_session_summarization(self, source_text: str) -> None:
        """Background summarization for the global session summary."""
        try:
            provider = self._summary_provider or os.environ.get("MEMORY_SUMMARY_PROVIDER") or os.environ.get("LLM_PROVIDER") or "openrouter"
            model = self._summary_model or os.environ.get("MEMORY_SUMMARY_MODEL") or os.environ.get("LLM_MODEL") or "openai/gpt-5-chat"
            max_chars = int(os.environ.get("MEMORY_SUMMARY_MAX_CHARS", str(self.max_context_length)))
            system_prompt = (
                "You are a game session summarizer. Maintain a coherent, evolving summary "
                "of all dialogues in the session, preserving key events, relationships, goals, and unresolved threads. "
                "Output plain text only."
            )
            user_prompt = (
                "Session Dialogue Log to date:\n" + source_text + "\n\n" +
                f"Write an updated unified session summary under ~{max_chars} characters. Merge duplicates and keep specifics."
            )
            new_summary = call_llm(provider, model, system_prompt, user_prompt, temperature=0.2, agent_name="session_summarizer")

            if self.current_session:
                with self._storage_lock:
                    self.current_session.session_summary = new_summary or ""
                    self.db_manager.update_session(self.current_session)
        except Exception as e:
            logger.error(f"Session summarization failed: {e}")
        finally:
            self._summarizing_session = False

    # ============================================================================
    # Day (Per-day) Memory Management
    # ============================================================================
    def append_day_summary(self, day: int, text: str) -> None:
        """Append text to the DayData.day_summary for the given day and summarize in background if needed."""
        if not self.current_session or not text:
            return
        dd = self.db_manager.get_day(self.current_session.session_id, day)
        if not dd:
            return
        sep = "\n" if (dd.day_summary or "") else ""
        dd.day_summary = (dd.day_summary or "") + sep + text
        self.db_manager.update_day(dd)

        try:
            # Use the same context threshold as session
            if len(dd.day_summary or "") > self.max_context_length:
                self._summarize_day_memory(day)
        except Exception:
            pass

    def _summarizing_days(self) -> set:
        # Lightweight per-instance cache (avoid attribute errors if not set)
        if not hasattr(self, "__summarizing_days_cache"):
            self.__summarizing_days_cache = set()
        return self.__summarizing_days_cache

    def _summarize_day_memory(self, day: int) -> None:
        if not self.current_session:
            return
        key = (self.current_session.session_id, day)
        if key in self._summarizing_days():
            return
        dd = self.db_manager.get_day(self.current_session.session_id, day)
        if not dd or not (dd.day_summary or "").strip():
            return
        self._summarizing_days().add(key)
        source_text = dd.day_summary or ""
        threading.Thread(
            target=self._run_day_summarization,
            args=(self.current_session.session_id, day, source_text),
            daemon=True,
        ).start()

    def _run_day_summarization(self, session_id: str, day: int, source_text: str) -> None:
        try:
            provider = getattr(self, "_summary_provider", None) or os.environ.get("MEMORY_SUMMARY_PROVIDER") or os.environ.get("LLM_PROVIDER") or "openrouter"
            model = getattr(self, "_summary_model", None) or os.environ.get("MEMORY_SUMMARY_MODEL") or os.environ.get("LLM_MODEL") or "openai/gpt-5-chat"
            max_chars = int(os.environ.get("MEMORY_SUMMARY_MAX_CHARS", str(self.max_context_length)))
            system_prompt = (
                "You are a day summarizer for a text-based RPG. Produce a coherent summary "
                "of this day's dialogues capturing key events, relationships, and unresolved items. Output plain text only."
            )
            user_prompt = (
                "Day Dialogue Log:\n" + source_text + "\n\n" +
                f"Write an updated day summary under ~{max_chars} characters. Merge duplicates and keep specifics."
            )
            new_summary = call_llm(provider, model, system_prompt, user_prompt, temperature=0.2, agent_name="day_summarizer")

            # Persist to the same day row
            dd = self.db_manager.get_day(session_id, day)
            if dd:
                with self._storage_lock:
                    dd.day_summary = new_summary or ""
                    self.db_manager.update_day(dd)
                # Notify listeners
                try:
                    self._notify_listeners('day_summarized', {
                        'session_id': session_id,
                        'day': day,
                        'summary_len': len(dd.day_summary or ""),
                    })
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Day summarization failed for session={session_id} day={day}: {e}")
        finally:
            try:
                self._summarizing_days().discard((session_id, day))
            except Exception:
                pass
    
    def get_all_npc_names(self) -> List[str]:
        """Get all NPC names from the current session's character list"""
        if not self.current_session or 'character_list' not in self.current_session.game_settings:
            return []
        
        return [char.get('name') for char in self.current_session.game_settings['character_list'] 
                if char.get('name') and char.get('type') == 'npc']

    def get_npc_opinion_db(self, npc_name: str, target_npc: str, session_id: str) -> Optional[str]:
        """Direct database wrapper for getting an NPC's opinion about another NPC"""
        if not session_id and self.current_session:
            session_id = self.current_session.session_id
        return self.db_manager.get_npc_opinion(npc_name, target_npc, session_id)
        
    def update_npc_opinion_db(self, npc_name: str, target_npc: str, opinion: str, session_id: str) -> bool:
        """Direct database wrapper for updating an NPC's opinion"""
        if not session_id and self.current_session:
            session_id = self.current_session.session_id
        return self.db_manager.update_npc_opinion(npc_name, target_npc, opinion, session_id)
        
    def insert_npc_opinion_db(self, npc_name: str, target_npc: str, opinion: str, session_id: str) -> bool:
        """Direct database wrapper for inserting a new opinion record"""
        if not session_id and self.current_session:
            session_id = self.current_session.session_id
        return self.db_manager.insert_npc_opinion(npc_name, target_npc, opinion, session_id)
        
    def get_active_npcs(self) -> List[Dict[str, Any]]:
        """Get active NPCs from the current session's database data only"""
        if not self.current_session:
            logger.warning("No current session - cannot get NPCs")
            return []
        
        # Only get NPCs that are stored in the current session's active_npcs list
        active_npc_names = self.current_session.active_npcs if self.current_session.active_npcs else []
        
        # Build detailed NPC list from database data only
        npcs = []
        for npc_name in active_npc_names:
            npc_memory = self.get_npc_memory(npc_name)
            if npc_memory and npc_memory.character_properties:
                npcs.append({
                    'name': npc_name,
                    'role': npc_memory.character_properties.get('role', 'Unknown'),
                    'story': npc_memory.character_properties.get('story', ''),
                    'personality': npc_memory.character_properties.get('personality', ''),
                    'locations': npc_memory.character_properties.get('locations', {}),
                })
            else:
                # If NPC is in session but has no memory data, include basic info
                logger.warning(f"NPC {npc_name} is in session but has no memory data")
                npcs.append({
                    'name': npc_name,
                    'role': 'Unknown',
                    'story': 'No data in session',
                    'personality': '',
                    'locations': {},
                })
        
        logger.info(f"Retrieved {len(npcs)} NPCs from session {self.current_session.session_id}")
        return npcs
