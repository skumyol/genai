"""
Database Manager for Game System
Handles all core database operations for the hierarchical game data structure
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from agents.dataclasses import (
    MainGameData, SessionData, DayData, Dialogue, Message, NPCMemory, TimePeriod
)


class DatabaseManager:
    """Core database manager that handles all database operations"""

    def __init__(self, db_path: str = None):
        if not db_path:
            # Default main database for frontend/user gameplay and analytics
            db_path = os.path.join(os.path.dirname(__file__), 'databases', 'maingamedata.db')
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        self._init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        # Use a sensible timeout to wait for locks instead of failing immediately.
        # Allow connections from multiple threads in the same process if needed.
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            # Improve concurrency: enable WAL mode and set busy timeout/synchronous level.
            try:
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL;")
                cur.execute("PRAGMA busy_timeout=30000;")
                cur.execute("PRAGMA synchronous=NORMAL;")
            except Exception:
                # If pragmas fail (older SQLite builds), continue with default behaviour.
                pass
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        """Initialize all database tables according to hierarchical structure"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Global ID counters for deterministic, incremental IDs starting at 0
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS id_counters (
                    entity TEXT PRIMARY KEY,
                    next_id INTEGER NOT NULL
                )
                """
            )

            # Main game data table - top level
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS main_game_data (
                    user_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    default_settings_path TEXT NOT NULL,
                    agent_settings_path TEXT NOT NULL,
                    session_ids TEXT,
                    metadata TEXT
                )
                """
            )

            # Sessions table - holds all session information
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    current_day INTEGER NOT NULL,
                    current_time_period TEXT NOT NULL,
                    game_settings TEXT,
                    agent_settings TEXT,
                    reputations TEXT,
                    session_summary TEXT,
                    active_npcs TEXT,
                    dialogue_ids TEXT
                )
                """
            )

            # Days table - a single row per (session_id, day)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS days (
                    session_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    time_period TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    dialogue_ids TEXT,
                    metadata TEXT,
                    active_npcs TEXT,
                    day_summary TEXT,
                    passive_npcs TEXT,
                    PRIMARY KEY (session_id, day),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )

            # Dialogues table - conversations between NPCs
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dialogues (
                    dialogue_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    initiator TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    time_period TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    message_ids TEXT,
                    summary TEXT,
                    summary_length INTEGER DEFAULT 0,
                    total_text_length INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )

            # Messages table - individual messages in dialogues
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    dialogue_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    sender_opinion TEXT,
                    receiver_opinion TEXT,
                    FOREIGN KEY (dialogue_id) REFERENCES dialogues(dialogue_id)
                )
                """
            )

            # NPC memories table - memory data per NPC per session
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS npc_memories (
                    npc_name TEXT,
                    session_id TEXT,
                    dialogue_ids TEXT,
                    messages_summary TEXT,
                    messages_summary_length INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    last_summarized TEXT,
                    opinion_on_npcs TEXT,
                    world_knowledge TEXT,
                    social_stance TEXT,
                    character_properties TEXT,
                    PRIMARY KEY (npc_name, session_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )

            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_game ON sessions(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_days_session ON days(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dialogues_session ON dialogues(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_dialogue ON messages(dialogue_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_npc_memories_session ON npc_memories(session_id)")

            # Metrics and analytics tables (centralized)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    session_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    time TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_metrics (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    total_time_ms INTEGER DEFAULT 0,
                    num_user_messages INTEGER DEFAULT 0,
                    num_npc_messages INTEGER DEFAULT 0,
                    num_keystrokes INTEGER DEFAULT 0,
                    approx_tokens_in INTEGER DEFAULT 0,
                    approx_tokens_out INTEGER DEFAULT 0,
                    imports_count INTEGER DEFAULT 0,
                    last_import_source TEXT,
                    last_started_at TEXT,
                    last_updated TEXT
                )
                """
            )

            conn.commit()

    def _get_next_id(self, entity: str) -> int:
        """Return the next integer ID for a given entity, starting at 0, and increment it atomically."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute("INSERT OR IGNORE INTO id_counters (entity, next_id) VALUES (?, 0)", (entity,))
            except sqlite3.OperationalError as e:
                if "no such table: id_counters" in str(e).lower():
                    # Create table inline and retry this connection
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS id_counters (entity TEXT PRIMARY KEY, next_id INTEGER NOT NULL)"
                    )
                    cur.execute("INSERT OR IGNORE INTO id_counters (entity, next_id) VALUES (?, 0)", (entity,))
                else:
                    raise
            # Current counter value
            cur.execute("SELECT next_id FROM id_counters WHERE entity = ?", (entity,))
            row = cur.fetchone()
            current = int(row[0]) if row else 0

            # If this is the first use (or counter was reset), align counter with existing rows
            try:
                baseline = None
                if entity == 'dialogues':
                    cur.execute("SELECT MAX(CAST(dialogue_id AS INTEGER)) FROM dialogues")
                    mx = cur.fetchone()
                    if mx and mx[0] is not None:
                        baseline = int(mx[0]) + 1
                elif entity == 'messages':
                    cur.execute("SELECT MAX(CAST(message_id AS INTEGER)) FROM messages")
                    mx = cur.fetchone()
                    if mx and mx[0] is not None:
                        baseline = int(mx[0]) + 1
                # Do not attempt to compute baselines for 'sessions' because IDs may be non-numeric
                if baseline is not None and baseline > current:
                    current = baseline
            except Exception:
                # If baseline check fails, proceed with existing counter
                pass

            # Reserve current and increment stored counter
            cur.execute("UPDATE id_counters SET next_id = ? WHERE entity = ?", (current + 1, entity))
            conn.commit()
            return current
    
    # ============================================================================
    # Main Game Data Operations
    # ============================================================================
    
    def create_main_game_data(self, user_id: Optional[str] = None, 
                             default_settings_path: str = "default_settings.json",
                             agent_settings_path: str = "agent_settings.json") -> MainGameData:
        """Create main game data entry"""
        if user_id is None or str(user_id).strip() == "":
            user_id = str(self._get_next_id('users'))
        
        main_data = MainGameData(
            user_id=user_id,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            default_settings_path=default_settings_path,
            agent_settings_path=agent_settings_path
        )
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO main_game_data 
                (user_id, created_at, last_updated, default_settings_path, 
                 agent_settings_path, session_ids, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    main_data.user_id,
                    main_data.created_at.isoformat(),
                    main_data.last_updated.isoformat(),
                    main_data.default_settings_path,
                    main_data.agent_settings_path,
                    json.dumps(main_data.session_ids),
                    json.dumps(main_data.metadata),
                ),
            )
            conn.commit()
        
        return main_data
    
    def get_main_game_data(self, user_id: str) -> Optional[MainGameData]:
        """Get main game data by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM main_game_data WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return MainGameData(
                    user_id=row['user_id'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_updated=datetime.fromisoformat(row['last_updated']),
                    default_settings_path=row['default_settings_path'],
                    agent_settings_path=row['agent_settings_path'],
                    session_ids=json.loads(row['session_ids'] or '[]'),
                    metadata=json.loads(row['metadata'] or '{}')
                )
        return None
    
    # ============================================================================
    # Session Operations
    # ============================================================================

    def create_session(self, session_id: Optional[str] = None,
                       game_settings: Dict[str, Any] = None,
                       agent_settings: Dict[str, Any] = None) -> SessionData:
        """Create a new game session"""
        if session_id is None or str(session_id).strip() == "":
            session_id = str(self._get_next_id('sessions'))

        session = SessionData(
            session_id=session_id,
            created_at=datetime.now(),
            last_updated=datetime.now(),
            current_day=1,
            current_time_period=TimePeriod.MORNING,
            game_settings=game_settings or {},
            agent_settings=agent_settings or {}
        )

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, created_at, last_updated, current_day, current_time_period,
                 game_settings, agent_settings, reputations, session_summary,
                 active_npcs, dialogue_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.created_at.isoformat(),
                    session.last_updated.isoformat(),
                    session.current_day,
                    session.current_time_period.value,
                    json.dumps(session.game_settings),
                    json.dumps(session.agent_settings),
                    json.dumps(session.reputations),
                    session.session_summary,
                    json.dumps(session.active_npcs),
                    json.dumps(session.dialogue_ids),
                ),
            )
            conn.commit()

        return session
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row:
                return SessionData(
                    session_id=row['session_id'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_updated=datetime.fromisoformat(row['last_updated']),
                    current_day=row['current_day'],
                    current_time_period=TimePeriod(row['current_time_period']),
                    game_settings=json.loads(row['game_settings'] or '{}'),
                    agent_settings=json.loads(row['agent_settings'] or '{}'),
                    reputations=json.loads(row['reputations'] or '{}'),
                    session_summary=row['session_summary'] or "",
                    active_npcs=json.loads(row['active_npcs'] or '[]'),
                    dialogue_ids=json.loads(row['dialogue_ids'] or '[]')
                )
        return None
    
    def update_session(self, session: SessionData) -> bool:
        """Update session data"""
        session.last_updated = datetime.now()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions SET
                last_updated = ?, current_day = ?, current_time_period = ?,
                game_settings = ?, agent_settings = ?, reputations = ?,
                session_summary = ?, active_npcs = ?, dialogue_ids = ?
                WHERE session_id = ?
            """, (
                session.last_updated.isoformat(),
                session.current_day,
                session.current_time_period.value,
                json.dumps(session.game_settings),
                json.dumps(session.agent_settings),
                json.dumps(session.reputations),
                session.session_summary,
                json.dumps(session.active_npcs),
                json.dumps(session.dialogue_ids),
                session.session_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def delete_session_data(self, session_id: str) -> None:
        """Delete a session and all related data (days, dialogues, messages, npc memories).
        Safe to call even if the session does not exist.
        """
        if not session_id:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Collect dialogue IDs for cascading delete of messages
            cursor.execute("SELECT dialogue_id FROM dialogues WHERE session_id = ?", (session_id,))
            rows = cursor.fetchall() or []
            dlg_ids = [r[0] for r in rows]
            if dlg_ids:
                # Chunk deletes to avoid parameter limits
                CHUNK = 500
                for i in range(0, len(dlg_ids), CHUNK):
                    chunk = dlg_ids[i:i+CHUNK]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor.execute(f"DELETE FROM messages WHERE dialogue_id IN ({placeholders})", tuple(chunk))
            # Delete dialogues, days, npc memories, then session
            cursor.execute("DELETE FROM dialogues WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM days WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM npc_memories WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
    
    # ============================================================================
    # Day Operations
    # ============================================================================
    
    def create_day(self, session_id: str, day: int, time_period: TimePeriod,
                   active_npcs: List[str] = None, passive_npcs: List[str] = None) -> DayData:
        """Create or upsert a day row (session_id, day)."""
        now = datetime.now()
        day_data = DayData(
            session_id=session_id,
            day=day,
            time_period=time_period,
            started_at=now,
            active_npcs=active_npcs or [],
            passive_npcs=passive_npcs or []
        )
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO days (
                    session_id, day, time_period, started_at, ended_at, dialogue_ids,
                    metadata, active_npcs, day_summary, passive_npcs
                ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, NULL, ?)
                ON CONFLICT(session_id, day) DO UPDATE SET
                    time_period=excluded.time_period,
                    active_npcs=excluded.active_npcs,
                    passive_npcs=excluded.passive_npcs
                """,
                (
                    day_data.session_id,
                    day_data.day,
                    day_data.time_period.value,
                    day_data.started_at.isoformat(),
                    json.dumps(day_data.dialogue_ids),
                    json.dumps(day_data.metadata),
                    json.dumps(day_data.active_npcs),
                    json.dumps(day_data.passive_npcs),
                ),
            )
            conn.commit()
        return day_data
    
    def get_day(self, session_id: str, day: int) -> Optional[DayData]:
        """Get a day by (session_id, day)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM days WHERE session_id = ? AND day = ?",
                (session_id, day),
            )
            row = cursor.fetchone()
            
            if row:
                return DayData(
                    session_id=row['session_id'],
                    day=row['day'],
                    time_period=TimePeriod(row['time_period']),
                    started_at=datetime.fromisoformat(row['started_at']),
                    ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                    dialogue_ids=json.loads(row['dialogue_ids'] or '[]'),
                    metadata=json.loads(row['metadata'] or '{}'),
                    active_npcs=json.loads(row['active_npcs'] or '[]'),
                    passive_npcs=json.loads(row['passive_npcs'] or '[]'),
                    day_summary=row['day_summary']
                )
        return None

    def update_day(self, day: DayData) -> bool:
        """Update an existing day entry by (session_id, day)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE days SET
                    ended_at = ?,
                    dialogue_ids = ?,
                    metadata = ?,
                    active_npcs = ?,
                    passive_npcs = ?,
                    day_summary = ?,
                    time_period = ?
                WHERE session_id = ? AND day = ?
                """,
                (
                    day.ended_at.isoformat() if day.ended_at else None,
                    json.dumps(day.dialogue_ids),
                    json.dumps(day.metadata),
                    json.dumps(day.active_npcs),
                    json.dumps(day.passive_npcs),
                    day.day_summary,
                    day.time_period.value,
                    day.session_id,
                    day.day,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
    
    # ============================================================================
    # Dialogue Operations
    # ============================================================================
    
    def create_dialogue(self, session_id: str, initiator: str, receiver: str,
                       location: str, day: int, time_period: TimePeriod) -> Dialogue:
        """Create a new dialogue"""
        # Deterministic sequential ID starting at 0
        dialogue_id = str(self._get_next_id('dialogues'))
        
        dialogue = Dialogue(
            dialogue_id=dialogue_id,
            session_id=session_id,
            initiator=initiator,
            receiver=receiver,
            day=day,
            location=location,
            time_period=time_period,
            started_at=datetime.now()
        )
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO dialogues
                    (dialogue_id, session_id, initiator, receiver, day, location, time_period,
                     started_at, ended_at, message_ids, summary, summary_length, total_text_length)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dialogue.dialogue_id,
                        dialogue.session_id,
                        dialogue.initiator,
                        dialogue.receiver,
                        dialogue.day,
                        dialogue.location,
                        dialogue.time_period.value,
                        dialogue.started_at.isoformat(),
                        dialogue.ended_at.isoformat() if dialogue.ended_at else None,
                        json.dumps(dialogue.message_ids),
                        dialogue.summary,
                        dialogue.summary_length,
                        dialogue.total_text_length,
                    ),
                )
            except sqlite3.OperationalError as e:
                if "no such table: dialogues" in str(e).lower():
                    self._init_database()
                    cursor.execute(
                        """
                        INSERT INTO dialogues
                        (dialogue_id, session_id, initiator, receiver, day, location, time_period,
                         started_at, ended_at, message_ids, summary, summary_length, total_text_length)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            dialogue.dialogue_id,
                            dialogue.session_id,
                            dialogue.initiator,
                            dialogue.receiver,
                            dialogue.day,
                            dialogue.location,
                            dialogue.time_period.value,
                            dialogue.started_at.isoformat(),
                            dialogue.ended_at.isoformat() if dialogue.ended_at else None,
                            json.dumps(dialogue.message_ids),
                            dialogue.summary,
                            dialogue.summary_length,
                            dialogue.total_text_length,
                        ),
                    )
                else:
                    raise
            conn.commit()
        
        return dialogue
    
    def get_dialogue(self, dialogue_id: str) -> Optional[Dialogue]:
        """Get dialogue by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dialogues WHERE dialogue_id = ?", (dialogue_id,))
            row = cursor.fetchone()
            
            if row:
                return Dialogue(
                    dialogue_id=row['dialogue_id'],
                    session_id=row['session_id'],
                    initiator=row['initiator'],
                    receiver=row['receiver'],
                    day=row['day'],
                    location=row['location'],
                    time_period=TimePeriod(row['time_period']),
                    started_at=datetime.fromisoformat(row['started_at']),
                    ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                    message_ids=json.loads(row['message_ids'] or '[]'),
                    summary=row['summary'],
                    summary_length=row['summary_length'] or 0,
                    total_text_length=row['total_text_length'] or 0
                )
        return None
    
    def update_dialogue(self, dialogue: Dialogue) -> bool:
        """Update dialogue data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE dialogues SET
                ended_at = ?, message_ids = ?, summary = ?, 
                summary_length = ?, total_text_length = ?
                WHERE dialogue_id = ?
            """, (
                dialogue.ended_at.isoformat() if dialogue.ended_at else None,
                json.dumps(dialogue.message_ids),
                dialogue.summary,
                dialogue.summary_length,
                dialogue.total_text_length,
                dialogue.dialogue_id
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    # ============================================================================
    # Message Operations
    # ============================================================================
    
    def create_message(self, dialogue_id: str, sender: str, receiver: str,
                      message_text: str, sender_opinion: Optional[str] = None,
                      receiver_opinion: Optional[str] = None) -> Message:
        """Create a new message"""
        # Deterministic sequential ID starting at 0
        message_id = str(self._get_next_id('messages'))
        
        message = Message(
            message_id=message_id,
            dialogue_id=dialogue_id,
            sender=sender,
            receiver=receiver,
            message_text=message_text,
            timestamp=datetime.now(),
            sender_opinion=sender_opinion,
            receiver_opinion=receiver_opinion
        )
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO messages
                    (message_id, dialogue_id, sender, receiver, message_text,
                     timestamp, sender_opinion, receiver_opinion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.message_id,
                        message.dialogue_id,
                        message.sender,
                        message.receiver,
                        message.message_text,
                        message.timestamp.isoformat(),
                        message.sender_opinion,
                        message.receiver_opinion,
                    ),
                )
            except sqlite3.OperationalError as e:
                # Auto-heal if messages table is missing (e.g., newly created DB file or migration gap)
                if "no such table: messages" in str(e).lower():
                    self._init_database()
                    cursor.execute(
                        """
                        INSERT INTO messages
                        (message_id, dialogue_id, sender, receiver, message_text,
                         timestamp, sender_opinion, receiver_opinion)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            message.message_id,
                            message.dialogue_id,
                            message.sender,
                            message.receiver,
                            message.message_text,
                            message.timestamp.isoformat(),
                            message.sender_opinion,
                            message.receiver_opinion,
                        ),
                    )
                else:
                    raise
            conn.commit()
        
        return message
    
    def get_messages_by_dialogue(self, dialogue_id: str) -> List[Message]:
        """Get all messages for a dialogue"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages 
                WHERE dialogue_id = ? 
                ORDER BY timestamp ASC
            """, (dialogue_id,))
            
            messages = []
            for row in cursor.fetchall():
                message = Message(
                    message_id=row['message_id'],
                    dialogue_id=row['dialogue_id'],
                    sender=row['sender'],
                    receiver=row['receiver'],
                    message_text=row['message_text'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    sender_opinion=row['sender_opinion'],
                    receiver_opinion=row['receiver_opinion']
                )
                messages.append(message)
            
            return messages
    
    # ============================================================================
    # NPC Memory Operations
    # ============================================================================
    
    def create_or_update_npc_memory(self, npc_memory: NPCMemory) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO npc_memories
                (npc_name, session_id, dialogue_ids, messages_summary,
                 messages_summary_length, created_at, last_updated, last_summarized,
                 opinion_on_npcs, world_knowledge, social_stance, character_properties)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    npc_memory.npc_name,
                    npc_memory.session_id,
                    json.dumps(npc_memory.dialogue_ids),
                    npc_memory.messages_summary,
                    npc_memory.messages_summary_length,
                    npc_memory.created_at.isoformat(),
                    npc_memory.last_updated.isoformat(),
                    npc_memory.last_summarized.isoformat() if npc_memory.last_summarized else None,
                    json.dumps(npc_memory.opinion_on_npcs),
                    json.dumps(npc_memory.world_knowledge),
                    json.dumps(npc_memory.social_stance),
                    json.dumps(npc_memory.character_properties),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_npc_memory(self, npc_name: str, session_id: str) -> Optional[NPCMemory]:
        """Get NPC memory for specific session (identified by npc_name)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM npc_memories 
                WHERE npc_name = ? AND session_id = ?
                """,
                (npc_name, session_id),
            )

            row = cursor.fetchone()
            if row:
                return NPCMemory(
                    npc_name=row['npc_name'],
                    session_id=row['session_id'],
                    dialogue_ids=json.loads(row['dialogue_ids'] or '[]'),
                    messages_summary=row['messages_summary'] or "",
                    messages_summary_length=row['messages_summary_length'] or 0,
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_updated=datetime.fromisoformat(row['last_updated']),
                    last_summarized=datetime.fromisoformat(row['last_summarized']) if row['last_summarized'] else None,
                    opinion_on_npcs=json.loads(row['opinion_on_npcs'] or '{}'),
                    world_knowledge=json.loads(row['world_knowledge'] or '{}'),
                    social_stance=json.loads(row['social_stance'] or '{}'),
                    character_properties=json.loads(row['character_properties'] or '{}') if 'character_properties' in row.keys() else {},
                )
        return None
    
    def get_npc_opinion(self, npc_name: str, target_npc: str, session_id: str) -> Optional[str]:
        """Get an NPC's opinion about a specific target NPC.
        
        Args:
            npc_name: Name of the NPC whose opinion we're checking
            target_npc: Name of the NPC being evaluated
            session_id: Current session ID
            
        Returns:
            The opinion text if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT json_extract(opinion_on_npcs, '$.' || ?) as opinion
                FROM npc_memories
                WHERE npc_name = ? AND session_id = ?
                """,
                (target_npc, npc_name, session_id),
            )
            row = cursor.fetchone()
            return row['opinion'] if row else None
    
    def update_npc_opinion(self, npc_name: str, target_npc: str, opinion: str, session_id: str) -> bool:
        """Update an NPC's opinion about a specific target NPC.
        
        Args:
            npc_name: Name of the NPC whose opinion we're updating
            target_npc: Name of the NPC being evaluated
            opinion: The new opinion text
            session_id: Current session ID
            
        Returns:
            True if update was successful, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE npc_memories
                SET opinion_on_npcs = json_set(
                    COALESCE(opinion_on_npcs, '{}'),
                    '$.' || ?,
                    ?
                )
                WHERE npc_name = ? AND session_id = ?
                """,
                (target_npc, opinion, npc_name, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def insert_npc_opinion(self, npc_name: str, target_npc: str, opinion: str, session_id: str) -> bool:
        """Insert a new opinion record for an NPC about another NPC.
        
        Args:
            npc_name: Name of the NPC whose opinion we're recording
            target_npc: Name of the NPC being evaluated
            opinion: The opinion text
            session_id: Current session ID
            
        Returns:
            True if insertion was successful, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # First check if NPC memory exists
            cursor.execute(
                "SELECT 1 FROM npc_memories WHERE npc_name = ? AND session_id = ?",
                (npc_name, session_id)
            )
            
            if not cursor.fetchone():
                return False
                
            # Update existing record with new opinion
            cursor.execute(
                """
                UPDATE npc_memories
                SET opinion_on_npcs = json_set(
                    COALESCE(opinion_on_npcs, '{}'),
                    '$.' || ?,
                    ?
                )
                WHERE npc_name = ? AND session_id = ?
                """,
                (target_npc, opinion, npc_name, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0
    
    # ============================================================================
    # Query Operations
    # ============================================================================
    
    def get_dialogues_by_session(self, session_id: str, day: Optional[int] = None,
                                time_period: Optional[TimePeriod] = None) -> List[Dialogue]:
        """Get dialogues for a session, optionally filtered by day/time"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM dialogues WHERE session_id = ?"
            params = [session_id]
            
            if day is not None:
                query += " AND day = ?"
                params.append(day)
            
            if time_period is not None:
                query += " AND time_period = ?"
                params.append(time_period.value)
            
            query += " ORDER BY started_at ASC"
            cursor.execute(query, params)
            
            dialogues = []
            for row in cursor.fetchall():
                dialogue = Dialogue(
                    dialogue_id=row['dialogue_id'],
                    session_id=row['session_id'],
                    initiator=row['initiator'],
                    receiver=row['receiver'],
                    day=row['day'],
                    location=row['location'],
                    time_period=TimePeriod(row['time_period']),
                    started_at=datetime.fromisoformat(row['started_at']),
                    ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                    message_ids=json.loads(row['message_ids'] or '[]'),
                    summary=row['summary'],
                    summary_length=row['summary_length'] or 0,
                    total_text_length=row['total_text_length'] or 0
                )
                dialogues.append(dialogue)
            
            return dialogues
    
    def get_npc_dialogues(self, npc_name: str, session_id: str, limit: int = 10) -> List[Dialogue]:
        """Get dialogues involving a specific NPC"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM dialogues
                WHERE session_id = ? AND (initiator = ? OR receiver = ?)
                ORDER BY started_at DESC
                LIMIT ?
            """, (session_id, npc_name, npc_name, limit))
            
            dialogues = []
            for row in cursor.fetchall():
                dialogue = Dialogue(
                    dialogue_id=row['dialogue_id'],
                    session_id=row['session_id'],
                    initiator=row['initiator'],
                    receiver=row['receiver'],
                    day=row['day'],
                    location=row['location'],
                    time_period=TimePeriod(row['time_period']),
                    started_at=datetime.fromisoformat(row['started_at']),
                    ended_at=datetime.fromisoformat(row['ended_at']) if row['ended_at'] else None,
                    message_ids=json.loads(row['message_ids'] or '[]'),
                    summary=row['summary'],
                    summary_length=row['summary_length'] or 0,
                    total_text_length=row['total_text_length'] or 0
                )
                dialogues.append(dialogue)
            
            return dialogues
