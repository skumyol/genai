"""
Dialogue Handler Module
Manages the execution of scheduled dialogues between NPCs with message and token limits.
"""

import asyncio
import os
import logging
import time
from typing import Optional, Any, List, Callable
from datetime import datetime
import json
from functools import wraps

from agents.dataclasses import Dialogue, Message
from agents.npc_agent import NPC_Agent
from agents.memory_agent import MemoryAgent
from agents.social_agents.opinion_agent import OpinionAgent
from agents.social_agents.social_stance_agent import SocialStanceAgent
from agents.social_agents.knowledge_agent import KnowledgeAgent
from agents.social_agents.reputation_agent import ReputationAgent

logger = logging.getLogger(__name__)

def count_tokens(text: str) -> int:
    """Simple token counter - estimates tokens as words * 1.3"""
    return int(len(text.split()) * 1.3)

def retry_on_failure(max_retries: int = 3, delay: float = 0.1, backoff: float = 2.0):
    """Decorator for retrying operations with exponential backoff"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

class DialogueHandlerError(Exception):
    """Base exception for dialogue handler errors"""
    pass

class MemoryOperationError(DialogueHandlerError):
    """Exception for memory operation failures"""
    pass

class DialogueStateError(DialogueHandlerError):
    """Exception for dialogue state inconsistencies"""
    pass

class DialogueHandler:
    """
    Handles the execution of dialogues between NPCs with proper lifecycle management.
    """
    
    def __init__(
        self,
        npc_agent: NPC_Agent,
        memory_agent: MemoryAgent,
        opinion_agent: Optional[OpinionAgent] = None,
        social_stance_agent: Optional[SocialStanceAgent] = None,
        knowledge_agent: Optional[KnowledgeAgent] = None,
        reputation_agent: Optional[ReputationAgent] = None,
        sse_manager: Optional[Any] = None,
        max_messages_per_dialogue: int = 10,
        max_tokens_per_dialogue: int = 2000,
        goodbye_threshold: int = 2,
        reputation_enabled: bool = True,
    ):
        """
        Initialize the DialogueHandler.
        
        Args:
            npc_agent: Stateless NPC agent for generating messages
            memory_agent: Memory agent for database operations
            opinion_agent: Optional opinion agent for opinion updates
            social_stance_agent: Optional social stance agent for stance updates
            knowledge_agent: Optional knowledge agent for knowledge updates
            sse_manager: Optional SSE manager for broadcasting messages
            max_messages_per_dialogue: Maximum messages per dialogue
            max_tokens_per_dialogue: Maximum tokens per dialogue
            goodbye_threshold: Number of goodbyes before ending dialogue
        """
        # Validate required dependencies
        if not npc_agent:
            raise ValueError("npc_agent is required")
        if not memory_agent:
            raise ValueError("memory_agent is required")
        
        self.npc_agent = npc_agent
        self.memory_agent = memory_agent
        self.opinion_agent = opinion_agent
        self.social_stance_agent = social_stance_agent
        self.knowledge_agent = knowledge_agent
        self.reputation_agent = reputation_agent
        self.reputation_enabled = bool(reputation_enabled)
        self.sse_manager = sse_manager
        self.max_messages_per_dialogue = max_messages_per_dialogue
        self.max_tokens_per_dialogue = max_tokens_per_dialogue
        self.goodbye_threshold = goodbye_threshold
        
        # Track active operations for consistency
        self._active_dialogues = set()
        # Lazily create the lock inside an active event loop
        self._memory_lock = None

    async def _get_memory_lock(self) -> asyncio.Lock:
        """Get or create the memory lock within a running event loop."""
        if self._memory_lock is None:
            self._memory_lock = asyncio.Lock()
        return self._memory_lock
        
    def _validate_dialogue_params(self, initiator_name: str, responder_name: str, phase: str):
        """Validate dialogue parameters"""
        if not initiator_name or not isinstance(initiator_name, str):
            raise ValueError("initiator_name must be a non-empty string")
        if not responder_name or not isinstance(responder_name, str):
            raise ValueError("responder_name must be a non-empty string")
        if initiator_name == responder_name:
            raise ValueError("initiator and responder must be different NPCs")
        if not phase or not isinstance(phase, str):
            raise ValueError("phase must be a non-empty string")
    
    @retry_on_failure(max_retries=3, delay=0.1)
    async def _safe_start_dialogue(self, initiator: str, receiver: str, location: str) -> Dialogue:
        """Safely start a dialogue with error handling"""
        try:
            # Run blocking DB call in a worker thread to avoid blocking the event loop
            dialogue = await asyncio.to_thread(
                self.memory_agent.start_dialogue,
                initiator=initiator,
                receiver=receiver,
                location=location,
            )
            if not dialogue or not dialogue.dialogue_id:
                raise MemoryOperationError("Failed to create dialogue: invalid dialogue returned")
            return dialogue
        except Exception as e:
            logger.error(f"Failed to start dialogue between {initiator} and {receiver}: {e}")
            raise MemoryOperationError(f"Could not start dialogue: {e}") from e
    
    @retry_on_failure(max_retries=3, delay=0.1)
    async def _safe_add_message(self, dialogue_id: str, sender: str, receiver: str, message_text: str) -> Message:
        """Safely add a message with error handling"""
        try:
            # Run blocking DB call in a worker thread to avoid blocking the event loop
            message = await asyncio.to_thread(
                self.memory_agent.add_message,
                dialogue_id=dialogue_id,
                sender=sender,
                receiver=receiver,
                message_text=message_text,
            )
            if not message or not message.message_id:
                raise MemoryOperationError("Failed to create message: invalid message returned")
            return message
        except Exception as e:
            logger.error(f"Failed to add message to dialogue {dialogue_id}: {e}")
            raise MemoryOperationError(f"Could not add message: {e}") from e
    
    @retry_on_failure(max_retries=3, delay=0.1)
    async def _safe_end_dialogue(self, dialogue_id: str, summary: Optional[str] = None) -> Dialogue:
        """Safely end a dialogue with error handling"""
        try:
            # Run blocking DB call in a worker thread to avoid blocking the event loop
            dialogue = await asyncio.to_thread(self.memory_agent.end_dialogue, dialogue_id, summary)
            return dialogue
        except Exception as e:
            logger.error(f"Failed to end dialogue {dialogue_id}: {e}")
            raise MemoryOperationError(f"Could not end dialogue: {e}") from e
    
    @retry_on_failure(max_retries=2, delay=0.2)
    async def _safe_update_conversation_context(self, npc_name: str, target_npc: str, context: str):
        """Safely update conversation context with error handling"""
        try:
            # Run blocking DB call in a worker thread to avoid blocking the event loop
            await asyncio.to_thread(self.memory_agent.update_npc_conversation_context, npc_name, target_npc, context)
        except Exception as e:
            logger.warning(f"Failed to update conversation context for {npc_name} -> {target_npc}: {e}")
            # Don't raise - this is non-critical
    
    async def execute_scheduled_dialogue(
        self,
        initiator_name: str,
        responder_name: str,
        location: Optional[str],
        phase: str,
    ) -> Dialogue:
        """
        Execute a scheduled dialogue between two NPCs.
        
        Args:
            initiator_name: Name of the initiating NPC
            responder_name: Name of the responding NPC
            location: Optional location of the dialogue
            phase: Current phase of the day
            
        Returns:
            The completed Dialogue object
        """
        # Validate input parameters
        self._validate_dialogue_params(initiator_name, responder_name, phase)
        
        logger.info(f"Starting dialogue between {initiator_name} and {responder_name} in phase {phase}")
        
        # Check for duplicate dialogue execution
        dialogue_key = f"{initiator_name}_{responder_name}_{phase}"
        if dialogue_key in self._active_dialogues:
            raise DialogueStateError(f"Dialogue already active: {dialogue_key}")
        
        self._active_dialogues.add(dialogue_key)
        dialogue = None
        
        try:
            # Create dialogue using MemoryAgent's API with error handling
            async with (await self._get_memory_lock()):
                dialogue = await self._safe_start_dialogue(
                    initiator=initiator_name,
                    receiver=responder_name,
                    location=location or ""
                )
            # Validate dialogue state after creation
            try:
                is_valid = await self._validate_dialogue_state(dialogue)
                if not is_valid:
                    logger.warning(f"Invalid dialogue state detected immediately after creation: {dialogue.dialogue_id}")
                    return dialogue
            except Exception as _:
                # Proceed; downstream checks and errors will handle edge cases
                pass
            
            logger.info(f"Dialogue created: {dialogue.dialogue_id}")
            # Track dialogue metrics
            message_count = 0
            total_tokens = 0
            goodbye_count = 0
            current_speaker_name = initiator_name
            current_listener_name = responder_name
            messages_created = []  # Track for cleanup on failure
            while (
                message_count < self.max_messages_per_dialogue and
                total_tokens < self.max_tokens_per_dialogue and
                goodbye_count < self.goodbye_threshold
            ):
                # Validate dialogue state before processing next turn
                try:
                    if not await self._validate_dialogue_state(dialogue):
                        logger.debug(f"Dialogue {dialogue.dialogue_id} no longer valid; ending loop")
                        break
                except Exception:
                    # Be conservative and end the loop on validation errors
                    break
                # Verify dialogue is still valid before each iteration
                if not dialogue or not dialogue.dialogue_id:
                    raise DialogueStateError("Dialogue became invalid during execution")
                # Check if we're approaching limits and should force goodbye
                # Also encourage quick wrap-up once any goodbye is observed
                force_goodbye = (
                    goodbye_count > 0 or
                    message_count >= self.max_messages_per_dialogue - 2 or
                    total_tokens >= self.max_tokens_per_dialogue * 0.9
                )
                last_message_id = None
                try:
                    # Generate message with timeout and error handling
                    message_text = await self._generate_npc_message(
                        speaker_name=current_speaker_name,
                        listener_name=current_listener_name,
                        dialogue=dialogue,
                        force_goodbye=force_goodbye
                    )
                    
                    if not message_text or not isinstance(message_text, str):
                        logger.warning(f"Invalid message generated by {current_speaker_name}, using fallback")
                        message_text = "I need to go now. Goodbye!"
                    
                    # Count tokens
                    message_tokens = count_tokens(message_text)
                    total_tokens += message_tokens
                    
                    # Check for goodbye indicators
                    if self._contains_goodbye(message_text):
                        goodbye_count += 1
                        logger.info(f"Goodbye detected ({goodbye_count}/{self.goodbye_threshold})")
                    
                    # Create message in database via MemoryAgent with error handling
                    async with (await self._get_memory_lock()):
                        message = await self._safe_add_message(
                            dialogue_id=dialogue.dialogue_id,
                            sender=current_speaker_name,
                            receiver=current_listener_name,
                            message_text=message_text
                        )
                        messages_created.append(message.message_id)
                        last_message_id = getattr(message, 'message_id', None)
                        # Compact per-message log line for readability
                        try:
                            preview = (message_text or "").replace('\n', ' ')[:120]
                            logger.info(
                                f"dlg {dialogue.dialogue_id} #{message_count + 1} "
                                f"{current_speaker_name}->{current_listener_name}: {preview}"
                            )
                        except Exception:
                            pass
                
                except Exception as e:
                    logger.error(f"Error processing message from {current_speaker_name}: {e}")
                    # Use fallback message to continue dialogue
                    message_text = "I need to go now. Goodbye!"
                    goodbye_count = self.goodbye_threshold  # Force end
                    
                    try:
                        async with (await self._get_memory_lock()):
                            message = await self._safe_add_message(
                                dialogue_id=dialogue.dialogue_id,
                                sender=current_speaker_name,
                                receiver=current_listener_name,
                                message_text=message_text
                            )
                            messages_created.append(message.message_id)
                            last_message_id = getattr(message, 'message_id', None)
                    except Exception as msg_error:
                        logger.error(f"Failed to add fallback message: {msg_error}")
                        break  # Exit dialogue loop
                
                # Broadcast message via SSE (non-critical)
                try:
                    await self._broadcast_message(
                        speaker_name=current_speaker_name,
                        listener_name=current_listener_name,
                        message=message_text,
                        phase=phase,
                        dialogue_id=dialogue.dialogue_id,
                        message_id=last_message_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to broadcast message: {e}")
                
                # Update conversation context in memory (non-critical)
                await self._safe_update_conversation_context(
                    current_speaker_name,
                    current_listener_name,
                    message_text
                )
                
                # Increment message count
                message_count += 1
                
                # Swap speaker and listener
                current_speaker_name, current_listener_name = current_listener_name, current_speaker_name
                
                # Add a small delay to simulate conversation flow
                await asyncio.sleep(0.5)
            
            # End dialogue and persist final state (no per-dialogue summary; session summary is built per-message)
            async with (await self._get_memory_lock()):
                dialogue = await self._safe_end_dialogue(dialogue.dialogue_id, None)
            
            # Post-dialogue updates for both agents using the same context snapshot
            try:
                await self._update_agents_after_dialogue(initiator_name, responder_name, dialogue)
            except Exception as e:
                logger.warning(f"Failed to run post-dialogue agent updates: {e}")

            # Optional: reputation updates (adds extra LLM calls when enabled)
            try:
                await self._maybe_update_reputation(initiator_name, responder_name, dialogue)
            except Exception as e:
                logger.warning(f"Failed to update reputation post-dialogue: {e}")
            
            logger.info(
                f"Dialogue completed successfully: {message_count} messages, "
                f"{total_tokens} tokens, {goodbye_count} goodbyes"
            )
            
        except Exception as e:
            logger.error(f"Critical error during dialogue execution: {e}")
            
            # Attempt cleanup
            if dialogue and dialogue.dialogue_id:
                try:
                    async with (await self._get_memory_lock()):
                        await self._safe_end_dialogue(dialogue.dialogue_id, None)
                    logger.info(f"Dialogue {dialogue.dialogue_id} ended with error cleanup")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup dialogue {dialogue.dialogue_id}: {cleanup_error}")
            
            raise DialogueHandlerError(f"Dialogue execution failed: {e}") from e
        
        finally:
            # Always cleanup tracking
            self._active_dialogues.discard(dialogue_key)
            
        return dialogue

    async def _maybe_update_reputation(self, npc1_name: str, npc2_name: str, dialogue: Dialogue):
        """Update reputations for both participants if enabled."""
        if not self.reputation_enabled or not self.reputation_agent:
            return
        try:
            world_def = self.memory_agent.get_world_description()
        except Exception:
            world_def = ""
        # Prepare dialogues text once
        dlg_text = await self._safe_extract_dialogue_content(dialogue)

        async def _update_one(name: str):
            try:
                cur = None
                try:
                    cur = (self.memory_agent.current_session.reputations or {}).get(name)
                except Exception:
                    cur = None
                opinions = {}
                try:
                    opinions = self.memory_agent.get_npc_all_opinions(name) or {}
                except Exception:
                    opinions = {}
                # Offload sync LLM call
                rep = await asyncio.to_thread(
                    self.reputation_agent.generate_reputation,
                    character_name=name,
                    world_definition=world_def,
                    opinions=opinions,
                    dialogues=dlg_text,
                    current_reputation=cur,
                )
                # Persist to session
                try:
                    self.memory_agent.current_session.reputations[name] = rep
                    await asyncio.to_thread(self.memory_agent.db_manager.update_session, self.memory_agent.current_session)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Reputation update failed for {name}: {e}")

        await asyncio.gather(_update_one(npc1_name), _update_one(npc2_name))
        
    async def _generate_npc_message(
        self,
        speaker_name: str,
        listener_name: str,
        dialogue: Dialogue,
        force_goodbye: bool = False
    ) -> str:
        """
        Generate a message from one NPC to another with robust error handling.
        
        Args:
            speaker_name: Name of the speaking NPC
            listener_name: Name of the listening NPC
            dialogue: Current dialogue object
            force_goodbye: Whether to force the NPC to say goodbye
            
        Returns:
            Generated message text
        """
        if not dialogue or not dialogue.dialogue_id:
            logger.error(f"Invalid dialogue object for message generation: {speaker_name} -> {listener_name}")
            return "I need to go now. Goodbye!"
        
        try:
            # Validate dialogue state before message generation
            if dialogue.ended_at:
                logger.warning(f"Attempting to generate message for ended dialogue {dialogue.dialogue_id}")
                return "I need to go now. Goodbye!"
            
            # Create a fresh dialogue copy to avoid state mutations during NPC agent call
            dialogue_copy = Dialogue(
                dialogue_id=dialogue.dialogue_id,
                session_id=dialogue.session_id,
                initiator=dialogue.initiator,
                receiver=dialogue.receiver,
                location=dialogue.location,
                day=dialogue.day,
                time_period=dialogue.time_period,
                started_at=dialogue.started_at,
                ended_at=dialogue.ended_at,
                message_ids=dialogue.message_ids.copy() if dialogue.message_ids else [],
                total_text_length=dialogue.total_text_length,
                summary=dialogue.summary,
                summary_length=dialogue.summary_length
            )
            
            # Offload synchronous LLM call to a thread and enforce a timeout
            timeout_s = float(os.environ.get("DIALOGUE_MESSAGE_TIMEOUT_SECONDS", "60"))
            message = await asyncio.wait_for(
                asyncio.to_thread(
                    self.npc_agent.generate_message,
                    npc_name=speaker_name,
                    partner_name=listener_name,
                    dialogue=dialogue_copy,
                    opinion_agent=self.opinion_agent,
                    # Defer social stance updates to end-of-dialogue to keep knowledge and stance in sync
                    social_stance_agent=None,
                    force_goodbye=force_goodbye,
                ),
                timeout=timeout_s,
            )
            
            # Validate generated message
            if not message or not isinstance(message, str):
                logger.warning(f"NPC agent returned invalid message type: {type(message)}")
                return "I need to go now. Goodbye!"
            
            # Sanitize message (basic safety). Do not clip; memory must remain full-fidelity.
            message = message.strip()
            
            return message
            
        except asyncio.TimeoutError:
            logger.error(
                f"Message generation timeout ({timeout_s}s) for {speaker_name} -> {listener_name} in dialogue {dialogue.dialogue_id}"
            )
            return "I need to go now. Goodbye!"
        except Exception as e:
            logger.error(f"Error generating message for {speaker_name}: {e}")
            return "I need to go now. Goodbye!"
            
    def _contains_goodbye(self, message: str) -> bool:
        """
        Check if a message contains goodbye indicators.
        
        Args:
            message: Message text to check
            
        Returns:
            True if message contains goodbye indicators
        """
        goodbye_phrases = [
            "goodbye", "bye", "farewell", "see you later",
            "see you", "talk later", "gotta go", "need to go",
            "have to go", "must go", "take care", "until next time"
        ]
        message_lower = message.lower()
        return any(phrase in message_lower for phrase in goodbye_phrases)
        
    def _get_npc_name(self, npc_name: str) -> str:
        """Compatibility helper: names are canonical; return input."""
        return npc_name
        
    async def _broadcast_message(
        self,
        speaker_name: str,
        listener_name: str,
        message: str,
        phase: str,
        *,
        dialogue_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ):
        """
        Broadcast a message via SSE.
        
        Args:
            speaker_id: ID of the speaker
            listener_id: ID of the listener
            message: Message text
            phase: Current phase
        """
        if self.sse_manager:
            try:
                payload = {
                    'dialogue_id': dialogue_id,
                    'message_id': message_id,
                    'speaker_name': speaker_name,
                    'listener_name': listener_name,
                    'message': message,
                    'phase': phase,
                    'timestamp': datetime.now().isoformat()
                }
                await self.sse_manager.send_event('dialogue_message', payload)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                
    async def _update_knowledge_after_dialogue(
        self,
        npc1_name: str,
        npc2_name: str,
        dialogue: Dialogue
    ):
        """
        Update knowledge for both NPCs after dialogue completion with robust error handling.
        
        Args:
            npc1_name: First NPC name
            npc2_name: Second NPC name
            dialogue: Completed dialogue
        """
        if not self.knowledge_agent:
            logger.debug("No knowledge agent available, skipping knowledge updates")
            return
        
        if not dialogue or not dialogue.dialogue_id:
            logger.warning("Invalid dialogue for knowledge update")
            return
            
        try:
            # Extract dialogue content with error handling
            dialogue_content = await self._safe_extract_dialogue_content(dialogue)
            if not dialogue_content:
                logger.warning(f"No dialogue content to analyze for {npc1_name} and {npc2_name}")
                return
            
            # Process each NPC separately to avoid one failure affecting the other
            await self._update_single_npc_knowledge(npc1_name, dialogue_content)
            await self._update_single_npc_knowledge(npc2_name, dialogue_content)
            
            logger.info(f"Knowledge update completed for {npc1_name} and {npc2_name}")
            
        except Exception as e:
            logger.error(f"Error updating knowledge after dialogue: {e}")

    async def _update_agents_after_dialogue(
        self,
        npc1_name: str,
        npc2_name: str,
        dialogue: Dialogue,
    ) -> None:
        """Update both Knowledge and Social Stance for both NPCs using the same dialogue context.

        Both agents receive the same snapshot: pre-update knowledge and the dialogue content.
        Then both updates are persisted to memory/DB via MemoryAgent.
        """
        # Extract dialogue content once
        dialogue_content = await self._safe_extract_dialogue_content(dialogue)
        if not dialogue_content:
            logger.warning(f"No dialogue content available for post-dialogue updates: {npc1_name}, {npc2_name}")
            return

        async def _prepare_personality(name: str) -> str:
            props = await asyncio.wait_for(
                asyncio.to_thread(self.memory_agent.get_character_properties, name),
                timeout=5.0,
            ) or {}
            raw = props.get('personality', '')
            try:
                return json.dumps(raw, ensure_ascii=False) if isinstance(raw, (dict, list)) else str(raw)
            except Exception:
                return str(raw)

        # Fetch shared inputs for both NPCs
        p1, p2 = await asyncio.gather(_prepare_personality(npc1_name), _prepare_personality(npc2_name))
        k1, k2 = await asyncio.gather(
            asyncio.to_thread(self.memory_agent.get_npc_world_knowledge, npc1_name),
            asyncio.to_thread(self.memory_agent.get_npc_world_knowledge, npc2_name),
        )
        k1 = k1 or {}
        k2 = k2 or {}

        # Run agents using pre-update knowledge
        updated_k1 = updated_k2 = None
        stance1 = stance2 = None

        # Knowledge updates (optional)
        if self.knowledge_agent:
            try:
                updated_k1, updated_k2 = await asyncio.gather(
                    asyncio.to_thread(
                        self.knowledge_agent.analyze_knowledge,
                        name=npc1_name,
                        personality=p1,
                        knowledge=k1,
                        dialogue=dialogue_content,
                    ),
                    asyncio.to_thread(
                        self.knowledge_agent.analyze_knowledge,
                        name=npc2_name,
                        personality=p2,
                        knowledge=k2,
                        dialogue=dialogue_content,
                    ),
                )
            except Exception as e:
                logger.warning(f"KnowledgeAgent error (post-dialogue): {e}")

        # Social stance updates (optional)
        if self.social_stance_agent:
            try:
                # Inputs for stance are derived from pre-update knowledge and conversation history
                rep1 = await asyncio.to_thread(self.memory_agent.get_npc_opinion, npc1_name, npc2_name)
                rep2 = await asyncio.to_thread(self.memory_agent.get_npc_opinion, npc2_name, npc1_name)
                opp_op1 = rep2  # what npc2 thinks of npc1
                opp_op2 = rep1  # what npc1 thinks of npc2
                hist1 = await asyncio.to_thread(self.memory_agent.get_npc_conversation_history, npc1_name, npc2_name)
                hist2 = await asyncio.to_thread(self.memory_agent.get_npc_conversation_history, npc2_name, npc1_name)
                dlg_mem1 = {npc2_name: hist1} if hist1 else {}
                dlg_mem2 = {npc1_name: hist2} if hist2 else {}

                stance1, stance2 = await asyncio.gather(
                    asyncio.to_thread(
                        self.social_stance_agent.set_social_stance,
                        npc_name=npc1_name,
                        npc_personality=p1,
                        opponent_name=npc2_name,
                        opponent_reputation=rep1,
                        opponent_opinion=opp_op1,
                        knowledge_base=k1,
                        dialogue_memory=dlg_mem1,
                        interaction_history=hist1,
                    ),
                    asyncio.to_thread(
                        self.social_stance_agent.set_social_stance,
                        npc_name=npc2_name,
                        npc_personality=p2,
                        opponent_name=npc1_name,
                        opponent_reputation=rep2,
                        opponent_opinion=opp_op2,
                        knowledge_base=k2,
                        dialogue_memory=dlg_mem2,
                        interaction_history=hist2,
                    ),
                )
            except Exception as e:
                logger.warning(f"SocialStanceAgent error (post-dialogue): {e}")

        # Persist updates atomically-ish under the handler lock
        try:
            async with (await self._get_memory_lock()):
                if updated_k1:
                    await asyncio.to_thread(self.memory_agent.update_npc_world_knowledge, npc1_name, updated_k1)
                if updated_k2:
                    await asyncio.to_thread(self.memory_agent.update_npc_world_knowledge, npc2_name, updated_k2)
                if stance1 is not None:
                    await asyncio.to_thread(self.memory_agent.update_npc_social_stance, npc1_name, {npc2_name: stance1})
                if stance2 is not None:
                    await asyncio.to_thread(self.memory_agent.update_npc_social_stance, npc2_name, {npc1_name: stance2})
        except Exception as e:
            logger.warning(f"Failed to persist post-dialogue agent updates: {e}")
    
    async def _update_single_npc_knowledge(self, npc_name: str, dialogue_content: str):
        """Update knowledge for a single NPC with error handling"""
        try:
            # Get NPC properties with timeout protection
            npc_props = await asyncio.wait_for(
                asyncio.to_thread(self.memory_agent.get_character_properties, npc_name),
                timeout=5.0
            ) or {}
            
            raw_personality = npc_props.get('personality', '')
            # Normalize personality to a compact JSON string for the KnowledgeAgent template
            try:
                if isinstance(raw_personality, (dict, list)):
                    npc_personality = json.dumps(raw_personality, ensure_ascii=False)
                else:
                    npc_personality = str(raw_personality)
            except Exception:
                npc_personality = str(raw_personality)
            
            # Get current knowledge with timeout protection
            npc_knowledge = await asyncio.wait_for(
                asyncio.to_thread(self.memory_agent.get_npc_world_knowledge, npc_name),
                timeout=5.0
            ) or {}
            
            # Analyze knowledge with timeout
            updated_knowledge = await asyncio.wait_for(
                asyncio.to_thread(
                    self.knowledge_agent.analyze_knowledge,
                    name=npc_name,
                    personality=npc_personality,
                    knowledge=npc_knowledge,
                    dialogue=dialogue_content
                ),
                timeout=30.0
            )
            
            if updated_knowledge:
                # Update knowledge with retry logic
                async with (await self._get_memory_lock()):
                    await asyncio.wait_for(
                        asyncio.to_thread(
                            self.memory_agent.update_npc_world_knowledge,
                            npc_name,
                            updated_knowledge
                        ),
                        timeout=10.0
                    )
                logger.debug(f"Knowledge updated for {npc_name}")
            else:
                logger.debug(f"No knowledge updates for {npc_name}")
                
        except asyncio.TimeoutError:
            logger.warning(f"Knowledge update timeout for {npc_name}")
        except Exception as e:
            logger.warning(f"Failed to update knowledge for {npc_name}: {e}")
            
    async def _safe_extract_dialogue_content(self, dialogue: Dialogue) -> str:
        """
        Safely extract content from a dialogue for knowledge updates.
        
        Args:
            dialogue: Dialogue object
            
        Returns:
            Formatted dialogue content
        """
        if not dialogue or not dialogue.dialogue_id:
            return ""
        
        try:
            # Fetch messages with timeout and retry protection
            messages = await asyncio.wait_for(
                asyncio.to_thread(self.memory_agent.get_dialogue_messages, dialogue.dialogue_id),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching messages for dialogue {dialogue.dialogue_id}")
            return ""
        except Exception as e:
            logger.warning(f"Error fetching dialogue messages: {e}")
            return ""
        
        if not messages:
            return ""
        
        try:
            content_parts = []
            # Add a compact metadata header for better context
            try:
                meta = []
                if getattr(dialogue, 'day', None) is not None:
                    meta.append(f"Day {dialogue.day}")
                tp = getattr(getattr(dialogue, 'time_period', None), 'value', None)
                if tp:
                    meta.append(tp)
                loc = getattr(dialogue, 'location', None)
                if loc:
                    meta.append(f"@ {loc}")
                participants = f"Participants: {dialogue.initiator} and {dialogue.receiver}"
                header = " | ".join([" ".join(meta), participants]).strip()
                if header:
                    content_parts.append(header)
            except Exception:
                pass
            for message in messages:
                if message and message.sender and message.message_text:
                    speaker = self._get_npc_name(message.sender)
                    # Sanitize message content
                    clean_text = message.message_text.replace('\n', ' ').strip()
                    if clean_text:
                        content_parts.append(f"{speaker}: {clean_text}")
            
            return "\n".join(content_parts) if content_parts else ""
            
        except Exception as e:
            logger.warning(f"Error formatting dialogue content: {e}")
            return ""
        
    async def clear_daily_conversation_contexts(self, npc_names: List[str]):
        """
        Clear daily conversation contexts for NPCs (lightweight cleanup).
        
        The automatic memory system handles summarization, so we only need
        to clear temporary conversation contexts at day end.
        
        Args:
            npc_names: List of NPC names to process
        """
        if not npc_names:
            logger.info("No NPCs to process for context cleanup")
            return
        
        logger.info(f"Clearing daily conversation contexts for {len(npc_names)} NPCs")
        
        success_count = 0
        import asyncio as _asyncio
        for npc_name in npc_names:
            try:
                # Clear daily conversation contexts without blocking the event loop
                await _asyncio.to_thread(self.memory_agent.clear_npc_conversation_context, npc_name)
                success_count += 1
                logger.debug(f"Cleared conversation context for {npc_name}")
            except Exception as e:
                logger.warning(f"Failed to clear context for {npc_name}: {e}")
        
        logger.info(f"Daily context cleanup completed: {success_count}/{len(npc_names)} successful")
        
        # Note: Memory summarization is handled automatically by the memory agent
        # when messages_summary exceeds max_context_length during dialogues
    
    def get_active_dialogue_count(self) -> int:
        """Get the number of currently active dialogues"""
        return len(self._active_dialogues)
    
    def is_dialogue_active(self, initiator_name: str, responder_name: str, phase: str) -> bool:
        """Check if a specific dialogue is currently active"""
        dialogue_key = f"{initiator_name}_{responder_name}_{phase}"
        return dialogue_key in self._active_dialogues
    
    async def force_end_all_dialogues(self, reason: str = "System shutdown"):
        """Force end all active dialogues (for cleanup)"""
        if not self._active_dialogues:
            return
        
        logger.warning(f"Force ending {len(self._active_dialogues)} active dialogues: {reason}")
        
        # Clear the set to prevent new dialogues
        active_keys = list(self._active_dialogues)
        self._active_dialogues.clear()
        
        logger.info(f"Cleared {len(active_keys)} active dialogue tracking entries")
    
    async def _validate_dialogue_state(self, dialogue: Dialogue) -> bool:
        """Validate that a dialogue is in a consistent state"""
        if not dialogue:
            return False
        
        try:
            # Check basic dialogue properties
            if not dialogue.dialogue_id or not dialogue.session_id:
                return False
            
            if not dialogue.initiator or not dialogue.receiver:
                return False
            
            # Check if dialogue has ended
            if dialogue.ended_at:
                logger.debug(f"Dialogue {dialogue.dialogue_id} has already ended")
                return False
            
            # Verify dialogue exists in memory agent
            async with (await self._get_memory_lock()):
                stored_dialogue = await asyncio.wait_for(
                    asyncio.to_thread(self.memory_agent.db_manager.get_dialogue, dialogue.dialogue_id),
                    timeout=5.0
                )
                
            if not stored_dialogue:
                logger.warning(f"Dialogue {dialogue.dialogue_id} not found in database")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating dialogue state: {e}")
            return False
