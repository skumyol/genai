from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional, Any
import json


class TimePeriod(Enum):
    """Time periods in the game"""
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"

"""
MainGameData holds all the sessions played
"""
@dataclass
class MainGameData:
    """Represents the main game data
    The logic: each user has one MainGameData instance that holds all their session data. A user can have multiple sessions.
    User can load any checkpoint from the session data or create a new session. If user loads a checkpoint,
    they are actually loading a specific version of the game state they can not modify it but all the session and its all subtables are cloned into
    a new instance that becomes unique session for the user. This is equivalent to the loading of a frozen checkpoint in game. 
    Metrics here holds a data structure for user gameplay. It holds all metrics measured per session. 
    """
    user_id: str
    created_at: datetime
    last_updated: datetime
    default_settings_path: str
    agent_settings_path: str
    session_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'default_settings_path': self.default_settings_path,
            'agent_settings_path': self.agent_settings_path,
            'session_ids': json.dumps(self.session_ids),
            'metadata': json.dumps(self.metadata)
        }


"""
SessionData holds all the data for a single session
"""
@dataclass
class SessionData:
    """Represents a game session with all its data.
    """
    session_id: str
    created_at: datetime
    last_updated: datetime
    current_day: int
    current_time_period: TimePeriod
    game_settings: Dict[str, Any]
    agent_settings: Dict[str, Any]
    reputations: Dict[str, Any] = field(default_factory=dict) # 
    session_summary: str = "" # this is a special summary of the session. Basically it is a summary of all the dialogues in the session but there is a catch, this will be part of the prompt for other LLMs therefore it will will be automatically summarised by a LLM when it exceeds a certain length, should happen in another thread asnyc so don't slow down the game 
    active_npcs: List[str] = field(default_factory=list)
    dialogue_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'current_day': self.current_day,
            'current_time_period': self.current_time_period.value,
            'game_settings': json.dumps(self.game_settings),
            'agent_settings': json.dumps(self.agent_settings),
            'reputations': json.dumps(self.reputations),
            'session_summary': self.session_summary,
            'active_npcs': json.dumps(self.active_npcs),
            'dialogue_ids': json.dumps(self.dialogue_ids),
        }


"""
NPCMemory holds all the data for a single NPC
"""
@dataclass
class NPCMemory:
    """Single large text content per NPC"""
    npc_name: str
    session_id: str
    dialogue_ids: List[str] = field(default_factory=list)
    messages_summary: str = "" # this is a special summary of the NPC. Basically it is a summary of all the dialogues in the session but there is a catch, this will be part of the prompt for other LLMs therefore it will will be automatically summarised by a LLM when it exceeds a certain length, should happen in another thread asnyc so don't slow down the game 
    messages_summary_length: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    last_summarized: Optional[datetime] = None
    opinion_on_npcs: Dict[str, Any] = field(default_factory=dict) # npc_name str pair
    world_knowledge: Dict[str, Any] = field(default_factory=dict) # This is a json object that contains the world knowledge of the NPC coming from knowledge agent
    social_stance: Dict[str, Any] = field(default_factory=dict) # This is a json object that contains the social stance of the NPC coming from social_stance_agent
    character_properties: Dict[str, Any] = field(default_factory=dict) # Immutable/base properties from default_settings.json (role, type, locations, life_cycle, story, personality)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'npc_name': self.npc_name,
            'session_id': self.session_id,
            'dialogue_ids': json.dumps(self.dialogue_ids),
            'messages_summary': self.messages_summary,
            'messages_summary_length': self.messages_summary_length,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'last_summarized': self.last_summarized.isoformat() if self.last_summarized else None,
            'opinion_on_npcs': json.dumps(self.opinion_on_npcs),
            'world_knowledge': json.dumps(self.world_knowledge),
            'social_stance': json.dumps(self.social_stance),
            'character_properties': json.dumps(self.character_properties),
        }

@dataclass
class DayData:
    """Represents the data for a single day in the game"""
    session_id: str
    day: int #incremental starting from 1
    time_period: TimePeriod
    started_at: datetime
    ended_at: Optional[datetime] = None
    dialogue_ids: List[str] = field(default_factory=list) # incremental starting from 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    active_npcs: List[str] = field(default_factory=list)
    passive_npcs: List[str] = field(default_factory=list)
    day_summary: Optional[str] = None # this is a special summary of the day. Basically it is a summary of all the dialogues in the day but there is a catch, this will be part of the prompt for other LLMs therefore it will will be automatically summarised by a LLM when it exceeds a certain length
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {     
            'session_id': self.session_id,
            'day': self.day,
            'time_period': self.time_period.value,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'dialogue_ids': json.dumps(self.dialogue_ids),
            'metadata': json.dumps(self.metadata),
            'active_npcs': json.dumps(self.active_npcs),
            'passive_npcs': json.dumps(self.passive_npcs),
            'day_summary': self.day_summary
        }



@dataclass
class Dialogue:
    """Represents a dialogue between NPCs"""
    dialogue_id: str
    session_id: str
    initiator: str # this is npcid  
    receiver: str # this is npcid
    day: int
    location: str
    time_period: TimePeriod
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_ids: List[str] = field(default_factory=list)
    summary: Optional[str] = None # this is a special summary of the dialogue. Basically it is a summary of all the messages in the dialogue but there is a catch, this will be part of the prompt for other LLMs therefore it will will be automatically summarised by a LLM when it exceeds a certain length, should happen in another thread asnyc so don't slow down the game 
    summary_length: int = 0
    total_text_length: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'dialogue_id': self.dialogue_id,
            'session_id': self.session_id,
            'initiator': self.initiator,
            'receiver': self.receiver,
            'day': self.day,
            'location': self.location,
            'time_period': self.time_period.value,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'message_ids': json.dumps(self.message_ids),
            'summary': self.summary,
            'summary_length': self.summary_length,
            'total_text_length': self.total_text_length
        }



@dataclass
class Message:
    """Represents a single message in a dialogue"""
    message_id: str
    dialogue_id: str
    sender: str
    receiver: str
    message_text: str
    timestamp: datetime
    sender_opinion: Optional[str] = None  # Text-based opinion generated by agent
    receiver_opinion: Optional[str] = None  # Text-based opinion generated by agent
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'message_id': self.message_id,
            'dialogue_id': self.dialogue_id,
            'sender': self.sender,
            'receiver': self.receiver,
            'message_text': self.message_text,
            'timestamp': self.timestamp.isoformat(),
            'sender_opinion': self.sender_opinion,
            'receiver_opinion': self.receiver_opinion
        }
    
    def __str__(self) -> str:
        return f"""{self.sender} said {self.message_text} to {self.receiver}. {self.sender}'s opinion on {self.receiver} was {self.sender_opinion}"""

