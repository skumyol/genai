import os
import json
import sqlite3
import uuid
import time
import random
import threading
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from flask import Flask, request, jsonify, Response, g
from flask_cors import CORS
from flask_socketio import SocketIO
from db_init import init_main_game_data

from agents.memory_agent import MemoryAgent
from game_loop_manager import GameLoopManager
from sse_manager import SSEManager
from dataclasses import dataclass
from deferred_routes import create_deferred_blueprint
from agents.social_agents.opinion_agent import OpinionAgent
from agents.social_agents.social_stance_agent import SocialStanceAgent
from agents.social_agents.knowledge_agent import KnowledgeAgent
from agents.social_agents.reputation_agent import ReputationAgent
from user_stats_manager import (
    log_session_start,
    log_session_stop,
    log_user_message,
    log_npc_message,
)
from avatar_provider import AvatarProvider, build_avatar_prompt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

def get_main_db_path() -> str:
    """Get the main database path from game_settings.json or fallback to default"""
    base = os.path.dirname(__file__)
    try:
        gs_path = os.path.join(base, 'game_settings.json')
        with open(gs_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f) or {}
        p = (((cfg.get('databases') or {}) if isinstance(cfg, dict) else {}).get('main'))
        if p:
            return p if os.path.isabs(p) else os.path.join(base, p)
    except Exception:
        pass
    # Fallback to configured default
    return os.path.join(base, 'databases', 'maingamedata.db')

def get_checkpoint_db_path() -> str:
    """Get the checkpoint database path from game_settings.json or fallback to default"""
    base = os.path.dirname(__file__)
    try:
        gs_path = os.path.join(base, 'game_settings.json')
        with open(gs_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f) or {}
        p = (((cfg.get('databases') or {}) if isinstance(cfg, dict) else {}).get('checkpoints'))
        if p:
            return p if os.path.isabs(p) else os.path.join(base, p)
    except Exception:
        pass
    # Fallback default
    return os.path.join(base, 'databases', 'checkpoints.db')

def migrate_legacy_database():
    """Migrate data from legacy game.db to new maingamedata.db location if needed"""
    old_path = os.path.join(os.path.dirname(__file__), 'game.db')
    new_path = get_main_db_path()
    
    # Only migrate if old DB exists and new DB doesn't exist
    if os.path.exists(old_path) and not os.path.exists(new_path):
        print(f"Migrating database from {old_path} to {new_path}")
        # Ensure the target directory exists
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        # Simple file copy for SQLite database
        import shutil
        shutil.copy2(old_path, new_path)
        print("Database migration completed")
        # Optionally backup the old file
        backup_path = old_path + '.backup'
        shutil.copy2(old_path, backup_path)
        print(f"Original database backed up to {backup_path}")

DB_PATH = get_main_db_path()
DEFAULT_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'default_settings.json')
API_PREFIX = '/api'

app = Flask(__name__)
# Allow common local dev origins for the Vite frontend
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://0.0.0.0:5173",
            ],
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        }
    },
    supports_credentials=True,
)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize SSE manager
sse_manager = SSEManager(socketio)

# Load default settings (file fallback) and DB-backed settings
def load_default_settings():
    """Load default game settings from JSON file"""
    try:
        with open(DEFAULT_SETTINGS_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {DEFAULT_SETTINGS_PATH} not found")
        return None

def load_settings_from_db(name: str = 'current') -> Optional[Dict[str, Any]]:
    """Load settings JSON from the DB `settings` table.

    Returns parsed dict if found, otherwise None.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM settings WHERE name = ?", (name,))
        row = cur.fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except Exception as e:
        logger.warning("Failed to load '%s' settings from DB: %s", name, e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return None

# Migrate legacy database if needed
migrate_legacy_database()

# Initialize memory agent - using configured main database
memory_agent = MemoryAgent(db_path=DB_PATH)

# Global game state for session management
game_sessions = {}
default_settings = load_default_settings()
# Runtime-configurable app settings (frontend/runner controlled)
app_runtime_config = {
    'reputation_auto_update': True,
    'reputation_update_timeout': 20.0,
    'social_agent_llms': {},   # {'opinion_agent': {'provider': '...', 'model': '...'}, ...}
    'game_agent_llms': {},     # {'dialogue_agent': {...}, 'lifecycle_agent': {...}, 'schedule_agent': {...}}
    'append_on_dialogue_end': False,  # per-message session summary is preferred
    'sse_enabled': False,      # disable SSE by default per UI requirements
}

# Track active player-driven chat dialogues per session and speaking NPC
# Structure: { session_id: { as_npc_name: dialogue_id } }
_player_chat_sessions: Dict[str, Dict[str, str]] = {}

# -----------------------------------------------------------------------------
# DB initialization for admin/settings
# -----------------------------------------------------------------------------
def _init_settings_table():
    """Create the settings table if missing and seed default/current rows."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                name TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

        # Seed defaults if not present
        now = datetime.utcnow().isoformat()
        default_cfg = default_settings or load_default_settings() or {}

        cur.execute("SELECT 1 FROM settings WHERE name='default'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO settings (name, value_json, updated_at) VALUES (?, ?, ?)",
                ("default", json.dumps(default_cfg), now),
            )

        cur.execute("SELECT 1 FROM settings WHERE name='current'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO settings (name, value_json, updated_at) VALUES (?, ?, ?)",
                ("current", json.dumps(default_cfg), now),
            )

        conn.commit()
    except Exception as e:
        logger.exception("Failed to initialize settings table: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

_init_settings_table()

# Initialize main_game_data table
init_main_game_data(DB_PATH, DEFAULT_SETTINGS_PATH, DEFAULT_SETTINGS_PATH.replace('default_settings.json', 'agent_settings.json'))

def _seed_npcs_for_session_from_settings(settings: Dict[str, Any]) -> None:
    """Ensure NPCs from settings.character_list are present in the session DB rows.

    - Sets session.active_npcs to active NPC names from settings
    - Creates npc_memories rows with character_properties for each NPC if missing
    """
    try:
        session = memory_agent.current_session
        if not session:
            return
        # Collect NPC definitions from both npc_templates and character_list (list or object)
        raw_cl = (settings or {}).get('character_list')
        cl: list = []
        if isinstance(raw_cl, list):
            cl = [c for c in raw_cl if isinstance(c, dict)]
        elif isinstance(raw_cl, dict):
            try:
                cl = [v for v in raw_cl.values() if isinstance(v, dict)]
            except Exception:
                cl = []
        tmpl = (settings or {}).get('npc_templates')
        if isinstance(tmpl, list):
            for t in tmpl:
                if isinstance(t, dict):
                    # Normalize template to character properties-like shape
                    c = t.copy()
                    c.setdefault('type', 'npc')
                    cl.append(c)

        # Pick active NPC names, default to include all NPCs
        active_names = []
        for c in cl:
            if not isinstance(c, dict):
                continue
            if (c.get('type') or 'npc') != 'npc':
                continue
            life = (c.get('life_cycle') or c.get('lifecycle') or c.get('lifeCycle') or 'active')
            try:
                life = str(life).lower()
            except Exception:
                life = 'active'
            if life == 'passive':
                # keep passive out of active lists but still seed memory rows
                pass
            else:
                active_names.append(c.get('name') or c.get('id'))

        # Update session.active_npcs and persist
        session.active_npcs = [n for n in active_names if n]
        try:
            memory_agent.db_manager.update_session(session)
        except Exception:
            pass

        # Ensure npc_memories exist with character_properties
        try:
            from agents.dataclasses import NPCMemory
            from datetime import datetime as _dt
        except Exception:
            NPCMemory = None
            _dt = None
        for c in cl:
            if not isinstance(c, dict) or not c.get('name'):
                continue
            name = c.get('name')
            mem = None
            try:
                mem = memory_agent.get_npc_memory(name)
            except Exception:
                mem = None
            if mem:
                # Backfill properties if missing
                try:
                    if not getattr(mem, 'character_properties', None):
                        mem.character_properties = c.copy()
                        memory_agent.db_manager.create_or_update_npc_memory(mem)
                except Exception:
                    pass
                continue
            # Create new memory row
            if NPCMemory and _dt:
                try:
                    cp = c.copy()
                    cp.setdefault('type', 'npc')
                    nm = NPCMemory(
                        npc_name=name,
                        session_id=session.session_id,
                        character_properties=cp,
                        created_at=_dt.now(),
                        last_updated=_dt.now(),
                    )
                    memory_agent.db_manager.create_or_update_npc_memory(nm)
                except Exception:
                    pass
        # Seed neutral opinions between all NPC pairs now that rows exist
        try:
            memory_agent.seed_neutral_opinions()
        except Exception:
            pass
    except Exception as e:
        logger.exception("Failed to seed NPCs for session: %s", e)

def _init_session_tables():
    """Create session and metrics tables if missing."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Session checkpoints
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS session_checkpoints (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                checkpoint_data BLOB NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )
        
        # Conversation metrics
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                dialogue_id TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                avg_response_time REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES session_checkpoints(session_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )
        
        # UX metrics
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ux_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                action TEXT NOT NULL,
                data_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(session_id) REFERENCES session_checkpoints(session_id)
            )
            """
        )
        
        conn.commit()
    except Exception as e:
        logger.exception("Failed to initialize session tables: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

_init_session_tables()

# Session management for game loops (defined later alongside streams)

# -----------------------------------------------------------------------------
# Helpers and globals
# -----------------------------------------------------------------------------

# Simple JSON helpers used by routes and blueprints
def ok(data: Any, code: int = 200):
    return jsonify(data), code


def err(message: str, code: int = 400):
    return jsonify({"error": message}), code


# Dataclass for validating game start payloads
@dataclass
class GameStartRequest:
    session_id: str
    num_days: Optional[int] = None


# Minimal in-memory game_state used by legacy chat/stream endpoints
game_state = {
    "status": "stopped",
    "day": 1,
    "time_period": "morning",
    "messages": [],
    "npc_updates": [],
}

# Lightweight social service wrapper to inject into deferred routes
class SocialService:
    def __init__(self, agent_llm_configs: Optional[Dict[str, Dict[str, str]]] = None):
        """Initialize social agents with optional per-agent LLM configs.

        agent_llm_configs keys should map to:
          - 'opinion_agent'
          - 'stance_agent'
          - 'knowledge_agent'
          - 'reputation_agent'

        Each value is a dict like {'provider': '...', 'model': '...'}
        If not provided, agents fall back to their JSON-config or 'test' defaults.
        """
        cfgs = agent_llm_configs or {}

        def _prov_model(key: str):
            cfg = cfgs.get(key) or {}
            return cfg.get('provider'), cfg.get('model')

        # OpinionAgent
        op_prov, op_model = _prov_model('opinion_agent')
        if op_prov or op_model:
            logger.info("SocialService: opinion_agent using provider=%s model=%s", op_prov or "(default)", op_model or "(default)")
            self._opinion = OpinionAgent(llm_provider=op_prov, llm_model=op_model)
        else:
            self._opinion = OpinionAgent()

        # SocialStanceAgent
        st_prov, st_model = _prov_model('stance_agent')
        if st_prov or st_model:
            logger.info("SocialService: stance_agent using provider=%s model=%s", st_prov or "(default)", st_model or "(default)")
            self._stance = SocialStanceAgent(llm_provider=st_prov, llm_model=st_model)
        else:
            self._stance = SocialStanceAgent()

        # KnowledgeAgent
        kn_prov, kn_model = _prov_model('knowledge_agent')
        if kn_prov or kn_model:
            logger.info("SocialService: knowledge_agent using provider=%s model=%s", kn_prov or "(default)", kn_model or "(default)")
            self._knowledge = KnowledgeAgent(llm_provider=kn_prov, llm_model=kn_model)
        else:
            self._knowledge = KnowledgeAgent()

        # ReputationAgent
        rp_prov, rp_model = _prov_model('reputation_agent')
        if rp_prov or rp_model:
            logger.info("SocialService: reputation_agent using provider=%s model=%s", rp_prov or "(default)", rp_model or "(default)")
            self._reputation = ReputationAgent(llm_provider=rp_prov, llm_model=rp_model)
        else:
            self._reputation = ReputationAgent()

    def reset_logs(self) -> None:
        """Reset logs for all social agents managed by this service."""
        try:
            if hasattr(self, "_opinion") and hasattr(self._opinion, "reset_log"):
                self._opinion.reset_log()
            if hasattr(self, "_stance") and hasattr(self._stance, "reset_log"):
                self._stance.reset_log()
            if hasattr(self, "_knowledge") and hasattr(self._knowledge, "reset_log"):
                self._knowledge.reset_log()
            if hasattr(self, "_reputation") and hasattr(self._reputation, "reset_log"):
                self._reputation.reset_log()
            logger.info("SocialService: all social agent logs have been reset")
        except Exception as e:
            logger.exception("SocialService.reset_logs failed: %s", e)

    def generate_opinion(
        self,
        *,
        name: str,
        personality: str,
        story: str,
        recipient: str,
        incoming_message: str = "",
        dialogue: str = "",
        recipient_reputation: Optional[str] = None,
    ) -> str:
        return self._opinion.generate_opinion(
            name=name,
            personality=personality,
            story=story,
            recipient=recipient,
            incoming_message=incoming_message,
            recipient_reputation=recipient_reputation,
            dialogue=dialogue,
        )

    def set_social_stance(
        self,
        *,
        npc_name,
        npc_personality,
        opponent_name,
        opponent_reputation,
        opponent_opinion,
        knowledge_base,
        dialogue_memory,
        interaction_history,
    ):
        return self._stance.set_social_stance(
            npc_name,
            npc_personality,
            opponent_name,
            opponent_reputation,
            opponent_opinion,
            knowledge_base,
            dialogue_memory,
            interaction_history,
        )

    def analyze_knowledge(self, *, name, personality, knowledge, dialogue) -> Dict[str, Any]:
        return self._knowledge.analyze_knowledge(name, personality, knowledge, dialogue)

    def generate_reputation(
        self,
        *,
        character_name: str,
        world_definition: str,
        opinions: Optional[Any],
        dialogues: str,
        current_reputation: Optional[str] = None,
    ) -> str:
        return self._reputation.generate_reputation(
            character_name=character_name,
            world_definition=world_definition,
            opinions=opinions,
            dialogues=dialogues,
            current_reputation=current_reputation,
        )


# Create and register deferred blueprint for memory/social/settings APIs
# Optionally read per-agent LLM configs for social agents from environment
_social_agent_llm_configs = None
_env_cfg = os.environ.get("GAME_AGENT_LLM_CONFIGS")
if _env_cfg:
    try:
        _social_agent_llm_configs = json.loads(_env_cfg)
        if not isinstance(_social_agent_llm_configs, dict):
            _social_agent_llm_configs = None
    except Exception:
        _social_agent_llm_configs = None

social_service = SocialService(agent_llm_configs=_social_agent_llm_configs)
 
# Database connection helper (must be defined before blueprint uses it)
def get_db():
    """Get database connection for current context"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

deferred_bp = create_deferred_blueprint(
    api_prefix=API_PREFIX,
    memory_agent=memory_agent,
    social_service=social_service,
    get_db=get_db,
    ok=ok,
    err=err,
    default_settings_path=DEFAULT_SETTINGS_PATH,
    default_settings=default_settings,
    game_sessions=game_sessions,
)
app.register_blueprint(deferred_bp)

# -----------------------------------------------------------------------------
# Reputation update on dialogue end (event listener)
# -----------------------------------------------------------------------------
def _on_memory_event(event_type: str, data: Dict[str, Any]):
    """Listen for dialogue end and update reputations for both participants."""
    try:
        if event_type != 'dialogue_ended' or not app_runtime_config.get('reputation_auto_update', True):
            return

        dialogue_data = (data or {}).get('dialogue_data') or {}
        dialogue_id = dialogue_data.get('dialogue_id') or data.get('dialogue_id')
        initiator = dialogue_data.get('initiator')
        receiver = dialogue_data.get('receiver')

        session = memory_agent.current_session
        if not session or not dialogue_id:
            return

        # Build dialogues text from messages for richer reputation signal
        try:
            msgs = memory_agent.get_dialogue_messages(dialogue_id) or []
            dialogues_text = "\n".join([f"{m.sender}: {m.message_text}" for m in msgs])
        except Exception:
            # Fallback to stored summary if messages unavailable
            dialogues_text = dialogue_data.get('summary') or ""

        world_def = memory_agent.get_world_description() or ""

        # Session summary is built per-message; optionally append at dialogue end if enabled
        if app_runtime_config.get('append_on_dialogue_end'):
            try:
                snippet = dialogue_data.get('summary') or dialogues_text
                stamp = f"[Day {dialogue_data.get('day')}] {initiator} ↔ {receiver}"
                memory_agent.append_session_summary(f"{stamp}: {snippet}")
            except Exception:
                pass

        # Update for both participants concurrently with timeout protection
        targets = [n for n in [initiator, receiver] if n]
        results: Dict[str, Optional[str]] = {}
        if targets:
            logger.info(
                "Reputation update start | session=%s dialogue=%s targets=%s",
                session.session_id,
                dialogue_id,
                targets,
            )
            start_ts = time.time()
            with ThreadPoolExecutor(max_workers=len(targets)) as executor:
                futures = []
                for name in targets:
                    def _task(n=name):
                        ops = memory_agent.get_npc_all_opinions(n)
                        cur = session.reputations.get(n)
                        # Enrich dialogues input with per-NPC long-term summary and session (global) summary
                        npc_summary = memory_agent.get_npc_dialogue_summary(n)
                        session_summary = memory_agent.get_accumulative_dialogue_memory()
                        dialogues_input = "\n\n".join([
                            (f"NPC summary for {n}:\n{npc_summary}" if npc_summary else ""),
                            (f"Recent dialogue:\n{dialogues_text}" if dialogues_text else ""),
                            (f"Session summary:\n{session_summary}" if session_summary else ""),
                        ]).strip()
                        rep = social_service.generate_reputation(
                            character_name=n,
                            world_definition=world_def,
                            opinions=ops,
                            dialogues=dialogues_input,
                            current_reputation=cur,
                        )
                        return n, rep
                    futures.append(executor.submit(_task))

                timeout_s = float(app_runtime_config.get('reputation_update_timeout', 20.0))
                try:
                    for fut in as_completed(futures, timeout=timeout_s):
                        try:
                            name, rep = fut.result()
                            results[name] = rep
                        except Exception as fe:
                            logger.exception("Reputation generation failed in future: %s", fe)
                except FuturesTimeoutError:
                    logger.warning(
                        "Reputation generation timed out after %.1fs (session=%s dialogue=%s)",
                        timeout_s,
                        session.session_id,
                        dialogue_id,
                    )

            # Apply successful results
            for k, v in results.items():
                session.reputations[k] = v or session.reputations.get(k)
            duration = time.time() - start_ts
            logger.info(
                "Reputation update end | session=%s dialogue=%s updated=%s duration=%.2fs",
                session.session_id,
                dialogue_id,
                list(results.keys()),
                duration,
            )

        # Persist session reputation updates
        try:
            memory_agent.db_manager.update_session(session)
        except Exception as e:
            logger.exception("Failed to persist session reputation updates: %s", e)

        # Optionally notify clients via SSE per session stream (disabled when SSE off)
        if app_runtime_config.get('sse_enabled', False):
            try:
                sse_manager.send_to_client(session.session_id, 'reputation_update', {
                    'dialogue_id': dialogue_id,
                    'reputations': {k: session.reputations.get(k) for k in filter(None, [initiator, receiver])},
                    'updated': list(results.keys()) if 'results' in locals() else [],
                    'pending': [n for n in [initiator, receiver] if n and (('results' in locals() and n not in results) or n not in session.reputations)],
                    'timestamp': datetime.utcnow().isoformat(),
                })
            except Exception:
                # Non-fatal if SSE not available
                pass
    except Exception as e:
        logger.exception("Reputation event listener error: %s", e)

# Helper to toggle reputation listener dynamically
_reputation_listener_active = False
def _update_reputation_listener():
    global _reputation_listener_active
    try:
        enabled = bool(app_runtime_config.get('reputation_auto_update', True))
        if enabled and not _reputation_listener_active:
            memory_agent.add_event_listener(_on_memory_event)
            _reputation_listener_active = True
            logger.info("Reputation auto-update listener registered (runtime)")
        elif not enabled and _reputation_listener_active:
            memory_agent.remove_event_listener(_on_memory_event)
            _reputation_listener_active = False
            logger.info("Reputation auto-update listener unregistered (runtime)")
    except Exception as e:
        logger.exception("Failed to update reputation listener: %s", e)

# Initialize listener according to current config
_update_reputation_listener()

# -----------------------------------------------------------------------------
# MemoryAgent -> SSE bridge (gameplay signals)
# -----------------------------------------------------------------------------
def _on_memory_signal(event_type: str, data: Dict[str, Any]):
    """Forward memory agent signals to frontend via SSE, per session.

    NPCs remain local-only; this is a pure broadcast of gameplay state.
    """
    try:
        # Honor runtime switch to fully disable SSE emissions
        if not app_runtime_config.get('sse_enabled', False):
            return
        session = memory_agent.current_session
        if not session:
            return
        session_id = session.session_id

        # Normalize a minimal session payload
        sess_info = {
            'session_id': session_id,
            'current_day': session.current_day,
            'time_period': session.current_time_period.value if session.current_time_period else None,
            'active_npcs': session.active_npcs,
        }

        # Suppress streaming of raw dialogue messages to the frontend.
        # Frontend should rely on DB reads and explicit chat responses instead.
        if event_type == 'message_added':
            return

        elif event_type in ('dialogue_started', 'dialogue_ended'):
            dlg = (data or {}).get('dialogue_data') or {}
            payload = {
                'event': event_type,
                'dialogue_id': dlg.get('dialogue_id'),
                'initiator': dlg.get('initiator'),
                'receiver': dlg.get('receiver'),
                'summary': dlg.get('summary'),
                'day': dlg.get('day', session.current_day),
                'time_period': dlg.get('time_period') or sess_info['time_period'],
            }
            sse_manager.send_to_client(session_id, 'dialogue_event', payload)

        elif event_type in ('npc_opinion_updated', 'npc_knowledge_updated', 'npc_memory_summarized'):
            payload = {'event': event_type, **(data or {})}
            sse_manager.send_to_client(session_id, 'npc_update', payload)

        elif event_type == 'character_added':
            ch = (data or {}).get('character_data') or {}
            sse_manager.send_to_client(session_id, 'npc_added', ch)

        elif event_type in ('time_advanced', 'day_created', 'session_created', 'session_loaded', 'day_updated'):
            sse_manager.send_to_client(session_id, 'session_update', sess_info)

        # Silent on other events
    except Exception as e:
        logger.exception("SSE bridge error for %s: %s", event_type, e)

# Register SSE bridge listener
try:
    if app_runtime_config.get('sse_enabled', False):
        memory_agent.add_event_listener(_on_memory_signal)
except Exception as e:
    logger.exception("Failed to register SSE bridge listener: %s", e)

# -----------------------------------------------------------------------------
# Simple SSE-based game loop
# -----------------------------------------------------------------------------

 

# Per-session broadcaster structures
_session_threads: Dict[str, threading.Thread] = {}
_session_stops: Dict[str, threading.Event] = {}


 


@app.route(f"{API_PREFIX}/chat", methods=['POST'])
def handle_chat():
    """Handle player-driven chat with active session tracking."""
    try:
        data = request.get_json(silent=True) or {}
        message = (data.get('message') or '').strip()
        as_npc = data.get('as_npc') or data.get('npc_name')
        to_npc = data.get('to_npc') or data.get('target_npc')
        user_id = (data.get('user_id') or '').strip() or None
        
        if not message or not as_npc or not to_npc:
            return jsonify({'error': 'message, as_npc, and to_npc are required'}), 400

        # Get active session for user
        session_id = _active_sessions.get(user_id)
        if not session_id:
            return jsonify({'error': 'no active session for user'}), 400

        # Load the active session
        if not memory_agent.load_session(session_id):
            return jsonify({'error': 'failed to load session'}), 400
            
        session = memory_agent.current_session
        # Optional user_id for metrics
        user_id = (data.get('user_id') or '').strip() or None

        # Auto-switch behavior: if user previously chatted as the same NPC with a different partner,
        # close that previous active dialogue to keep state clean.
        try:
            sess_map = _player_chat_sessions.setdefault(session.session_id, {})
            prev_did = sess_map.get(as_npc)
            if prev_did and prev_did in memory_agent.active_dialogues:
                prev_d = memory_agent.active_dialogues.get(prev_did)
                if prev_d and not getattr(prev_d, 'ended_at', None):
                    prev_partner = prev_d.receiver if prev_d.initiator == as_npc else prev_d.initiator
                    if prev_partner != to_npc:
                        try:
                            memory_agent.end_dialogue(prev_did)
                            logger.info(
                                "Player chat: ended previous dialogue %s (%s <-> %s) due to partner switch to %s",
                                prev_did, prev_d.initiator, prev_d.receiver, to_npc,
                            )
                            # SSE conversation event broadcasting removed
                        except Exception:
                            pass
                        finally:
                            try:
                                del sess_map[as_npc]
                            except Exception:
                                pass
        except Exception:
            pass

        # Find an existing active dialogue between these two NPCs, otherwise start a new one
        try:
            dialogue = None
            try:
                for d in memory_agent.active_dialogues.values():
                    if not d or getattr(d, 'ended_at', None):
                        continue
                    # Match regardless of direction (as_npc <-> to_npc)
                    if (d.initiator == as_npc and d.receiver == to_npc) or (d.initiator == to_npc and d.receiver == as_npc):
                        dialogue = d
                        break
            except Exception:
                dialogue = None
            if not dialogue:
                location = memory_agent.get_location(to_npc)
                dialogue = memory_agent.start_dialogue(initiator=as_npc, receiver=to_npc, location=location)
            # Remember active player chat dialogue for this speaker NPC
            try:
                _player_chat_sessions.setdefault(session.session_id, {})[as_npc] = dialogue.dialogue_id
            except Exception:
                pass
            # SSE conversation broadcasting removed - frontend handles state directly
        except Exception as e:
            logger.exception('Failed to initialize dialogue: %s', e)
            return jsonify({'error': 'failed to init dialogue'}), 500

        # Add player's message (as the speaking NPC)
        try:
            memory_agent.add_message(dialogue.dialogue_id, sender=as_npc, receiver=to_npc, message_text=message)
            # Stats: user message
            try:
                ks = None
                try:
                    ks = int((data.get('keystrokes') or 0))
                except Exception:
                    ks = None
                tokens_override = None
                try:
                    tokens_override = int((data.get('approx_tokens') or 0)) or None
                except Exception:
                    tokens_override = None
                from user_stats_manager import log_user_message as _lum
                _lum(getattr(memory_agent.db_manager, 'db_path', None), session.session_id, message, ks, tokens_override, user_id)
            except Exception:
                pass
            # SSE broadcasting removed - frontend handles messages directly
        except Exception as e:
            logger.exception('Failed to add player message: %s', e)
            return jsonify({'error': 'failed to record message'}), 500

        # Generate NPC response using the stateless NPC agent; derive LLM config
        try:
            from agents.npc_agent import NPC_Agent
            # Configure NPC agent from runtime config if supplied; otherwise infer from session's experiment
            agent_cfg = app_runtime_config.get('game_agent_llms') or {}
            dlg_cfg = agent_cfg.get('dialogue_agent') or {}
            prov = dlg_cfg.get('provider')
            modl = dlg_cfg.get('model')
            if not (prov and modl):
                try:
                    # First, try to read LLM config directly from session's game_settings (for imported checkpoints)
                    gs = session.game_settings or {}
                    ga = gs.get('game_agents') or {}
                    dd = ga.get('dialogue_agent') or {}
                    prov = prov or dd.get('provider') or gs.get('llm_provider')
                    modl = modl or dd.get('model') or gs.get('llm_model')
                    if not (prov and modl):
                        # Fallback to experimental_config.json using current session's experiment metadata
                        exp = gs.get('experiment') or {}
                        exp_name = exp.get('experiment_name')
                        var_id = exp.get('variant_id')
                        if exp_name and var_id:
                            cfg_path = os.path.join(os.path.dirname(__file__), 'experimental_config.json')
                            with open(cfg_path, 'r', encoding='utf-8') as f:
                                conf = json.load(f)
                            v = None
                            for _, econf in (conf.get('experiments') or {}).items():
                                if econf.get('name') and True:  # iterate all and match by id
                                    for vv in econf.get('variants', []):
                                        if vv.get('id') == var_id:
                                            v = vv
                                            break
                                    if v:
                                        break
                        if v:
                            ga = (v.get('config') or {}).get('game_agents') or {}
                            dd = ga.get('dialogue_agent') or {}
                            prov = prov or dd.get('provider')
                            modl = modl or dd.get('model')
                except Exception:
                    pass
            
            # Update social agents' LLM configs from session's game_settings if available
            gs = session.game_settings or {}
            sa = gs.get('social_agents') or {}
            def _apply_social(agent_attr: str, key: str):
                cfg = sa.get(key) or {}
                prov = cfg.get('provider')
                model = cfg.get('model')
                agent = getattr(social_service, agent_attr, None)
                if agent and hasattr(agent, 'set_llm_provider') and (prov or model):
                    agent.set_llm_provider(prov or 'test', model or 'test')
            _apply_social('_opinion', 'opinion_agent')
            _apply_social('_stance', 'social_stance_agent')
            _apply_social('_knowledge', 'knowledge_agent')
            _apply_social('_reputation', 'reputation_agent')
            
            npc_agent = NPC_Agent(memory_agent=memory_agent, llm_provider=prov or 'openrouter', llm_model=modl or 'meta-llama/llama-3.2-3b-instruct:free')
            # Pass social agents
            response_text = npc_agent.generate_message(
                npc_name=to_npc,
                partner_name=as_npc,
                dialogue=dialogue,
                opinion_agent=getattr(social_service, '_opinion', None),
                social_stance_agent=getattr(social_service, '_stance', None),
                force_goodbye=False,
            )
            response_text = (response_text or '').strip()
            if not response_text:
                response_text = "I need to go now. Goodbye!"
        except Exception as e:
            logger.exception('NPC response generation failed: %s', e)
            response_text = "I need to go now. Goodbye!"

        # Persist NPC response
        try:
            memory_agent.add_message(dialogue.dialogue_id, sender=to_npc, receiver=as_npc, message_text=response_text)
            # Stats: npc message
            try:
                from user_stats_manager import log_npc_message as _lnm
                _lnm(getattr(memory_agent.db_manager, 'db_path', None), session.session_id, response_text, user_id)
            except Exception:
                pass
            # SSE broadcasting removed - frontend handles messages directly
        except Exception as e:
            logger.exception('Failed to add NPC response message: %s', e)

        # Record conversation metrics
        _record_conversation_metrics(dialogue.dialogue_id, user_id, session.session_id)

        # Record UX metrics
        _record_ux_metrics(user_id, session.session_id, "chat_message", {
            "npc": as_npc,
            "target": to_npc,
            "message_length": len(message),
            "keystrokes": data.get('keystrokes')
        })

        return jsonify({
            'success': True,
            'session_id': session.session_id,
            'dialogue_id': dialogue.dialogue_id,
            'response': {
                'message': response_text,
                'speaker': to_npc,
                'listener': as_npc,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.exception('Chat handler error: %s', e)
        return jsonify({'error': 'internal server error'}), 500

def _record_conversation_metrics(dialogue_id: str, user_id: str, session_id: str):
    """Record conversation metrics to database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Get message count and avg response time
        messages = memory_agent.get_dialogue_messages(dialogue_id) or []
        message_count = len(messages)
        
        # Calculate response times if we have enough messages
        response_times = []
        for i in range(1, len(messages)):
            prev_raw = messages[i-1].timestamp
            curr_raw = messages[i].timestamp
            prev_time = prev_raw if not isinstance(prev_raw, str) else datetime.fromisoformat(prev_raw)
            curr_time = curr_raw if not isinstance(curr_raw, str) else datetime.fromisoformat(curr_raw)
            response_times.append((curr_time - prev_time).total_seconds())
            
        avg_response_time = sum(response_times)/len(response_times) if response_times else None
        
        # Insert metrics
        cur.execute(
            """
            INSERT INTO conversation_metrics (
                session_id, user_id, dialogue_id, 
                message_count, avg_response_time, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, user_id, dialogue_id,
                message_count, avg_response_time,
                datetime.utcnow().isoformat()
            )
        )
        
        conn.commit()
    except Exception as e:
        logger.exception("Failed to record conversation metrics: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

def _record_ux_metrics(user_id: str, session_id: str, action: str, data: dict):
    """Record UX metrics to database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO ux_metrics (
                user_id, session_id, action, 
                data_json, timestamp
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id, session_id, action,
                json.dumps(data), datetime.utcnow().isoformat()
            )
        )
        
        conn.commit()
    except Exception as e:
        logger.exception("Failed to record UX metrics: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

@app.get(f"{API_PREFIX}/stream")
def stream():
    """SSE endpoint for real-time updates"""
    # Fully disabled when SSE is off
    if not app_runtime_config.get('sse_enabled', False):
        return err('SSE disabled', 404)
    def generate():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to game stream'})}\n\n"
        
        last_state = {}
        last_message_count = 0
        
        # Keep connection alive and send updates
        while True:
            time.sleep(0.5)  # Check more frequently for updates
            
            # Send game state updates if changed
            current_state = {
                'status': game_state.get('status', 'stopped'),
                'day': game_state.get('day', 1),
                'time_period': game_state.get('time_period', 'morning')
            }
            
            if current_state != last_state:
                update = {
                    'type': 'game_state',
                    **current_state,
                    'timestamp': datetime.utcnow().isoformat()
                }
                yield f"data: {json.dumps(update)}\n\n"
                last_state = current_state.copy()
            
            # Send new messages if any
            messages = game_state.get('messages', [])
            if len(messages) > last_message_count:
                new_messages = messages[last_message_count:]
                for msg in new_messages:
                    yield f"data: {json.dumps({'type': 'message', 'message': msg})}\n\n"
                last_message_count = len(messages)
            
            # Send NPC status updates
            if game_state.get('npc_updates'):
                for update in game_state['npc_updates']:
                    yield f"data: {json.dumps({'type': 'npc_update', **update})}\n\n"
                game_state['npc_updates'] = []
            
            # Send heartbeat every 10 iterations (5 seconds)
            if int(time.time()) % 5 == 0:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
    
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response


@app.get(f"{API_PREFIX}/stream/<session_id>")
def stream_session(session_id: str):
    """SSE endpoint bound to a specific session/client ID using SSEManager."""
    # Fully disabled when SSE is off
    if not app_runtime_config.get('sse_enabled', False):
        return err('SSE disabled', 404)
    def generate():
        for chunk in sse_manager.stream_events(session_id):
            yield chunk
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response


def _run_conversation_with_sse(game_loop, initiator, recipient, phase, day, sse_manager):
    """Run a conversation between NPCs and broadcast via SSE"""
    logger.info(f"Starting conversation: {initiator} -> {recipient}")
    # Skip broadcasting when SSE is disabled
    if app_runtime_config.get('sse_enabled', False):
        sse_manager.broadcast('conversation_event', {
            'type': 'conversation_start',
            'initiator': initiator,
            'recipient': recipient,
            'phase': phase,
            'day': day
        })
    
    # Run the conversation
    messages = game_loop.run_conversation(initiator, recipient, phase)
    
    # Broadcast each message
    for message in messages:
        if app_runtime_config.get('sse_enabled', False):
            sse_manager.broadcast('conversation_event', {
                'type': 'message',
                'sender': message.sender,
                'recipient': message.recipient,
                'text': message.text,
                'phase': phase,
                'day': day
            })
            time.sleep(0.5)  # Small delay between messages
    
    # Broadcast conversation end
    if app_runtime_config.get('sse_enabled', False):
        sse_manager.broadcast('conversation_event', {
            'type': 'conversation_end',
            'initiator': initiator,
            'recipient': recipient,
            'phase': phase,
            'day': day,
            'message_count': len(messages)
        })

def _advance_period(periods: list[str], current: str) -> tuple[str, bool]:
    if current not in periods:
        return periods[0], False
    idx = periods.index(current)
    if idx < len(periods) - 1:
        return periods[idx + 1], False
    return periods[0], True  # wrapped to next day

def _broadcast(session_id: str, data: dict):
    """Broadcast data to a specific session"""
    if app_runtime_config.get('sse_enabled', False):
        sse_manager.send_to_client(session_id, 'session_update', data)


def _game_loop(session_id: str, num_days: int, tick_seconds: float = 3.0):
    stop_event = _session_stops[session_id]
    # Create application context for this thread
    with app.app_context():
        logger.info(f"Starting game loop for session {session_id}, {num_days} days")
        
        # Ensure a session exists in MemoryAgent using DB-backed settings
        if not memory_agent.current_session or memory_agent.current_session.session_id != session_id:
            logger.info(f"Creating new session {session_id}")
            db_settings = load_settings_from_db('current') or load_settings_from_db('default')
            settings_to_use = db_settings if db_settings is not None else (default_settings or {})
            memory_agent.create_session(session_id=session_id, game_settings=settings_to_use)
            try:
                _seed_npcs_for_session_from_settings(settings_to_use)
            except Exception:
                pass
        
        # Mark running in app-level broadcast
        session = memory_agent.current_session
        current_day = session.current_day if session else 1
        current_time_period = session.current_time_period.value if session and session.current_time_period else "morning"
        
        logger.info(f"Session {session_id} starting at day {current_day}, time period {current_time_period}")
        _broadcast(session_id, {
            "type": "state", 
            "game_state": "running", 
            "current_day": current_day, 
            "time_period": current_time_period
        })

        # Initialize game loop manager with SSE manager and stop signal
        try:
            # Read per-agent LLM configs from runtime-configurable state (frontend/runner controlled)
            agent_llm_configs = app_runtime_config.get('game_agent_llms') or None

            game_loop = GameLoopManager(
                memory_agent,
                sse_manager=sse_manager,
                stop_event=stop_event,
                agent_llm_configs=agent_llm_configs,
            )
            game_loop.current_day = current_day
            logger.info(f"GameLoopManager initialized successfully for session {session_id}")
        except Exception as e:
            logger.exception(f"Failed to initialize GameLoopManager for session {session_id}: %s", e)
            _broadcast(session_id, {"type": "error", "message": "Failed to initialize game loop"})
            return

        days_run = 0
        while not stop_event.is_set() and days_run < num_days:
            logger.info(f"Session {session_id}: Starting day {game_loop.current_day} (run {days_run + 1}/{num_days})")
            
            # Run one day cycle asynchronously
            try:
                # Log lifecycle and schedule agent calls at beginning of day
                logger.info(f"Session {session_id}: Calling lifecycle and schedule agents for day {game_loop.current_day}")
                
                asyncio.run(game_loop.run_day_cycle())
                
                logger.info(f"Session {session_id}: Completed day {game_loop.current_day} successfully")
                
            except Exception as e:
                logger.exception(f"Session {session_id}: Game day cycle error on day {game_loop.current_day}: %s", e)
                _broadcast(session_id, {
                    "type": "error", 
                    "message": f"Error on day {game_loop.current_day}: {str(e)}",
                    "day": game_loop.current_day
                })
                break

            # Only advance counters and broadcast tick if not stopping mid-cycle
            if not stop_event.is_set():
                days_run += 1
                # Update session day count
                try:
                    memory_agent.advance_time(new_day=game_loop.current_day)
                    logger.info(f"Session {session_id}: Advanced to day {game_loop.current_day}")
                except Exception as e:
                    logger.exception(f"Session {session_id}: Error advancing time: %s", e)
                
                _broadcast(session_id, {
                    "type": "tick", 
                    "current_day": game_loop.current_day,
                    "days_completed": days_run,
                    "days_remaining": num_days - days_run
                })

        # finalize
        final_day = game_loop.current_day
        logger.info(f"Session {session_id}: Game loop completed. Final day: {final_day}, Days run: {days_run}")
        _broadcast(session_id, {
            "type": "end", 
            "game_state": "stopped", 
            "current_day": final_day,
            "total_days_run": days_run,
            "completed_successfully": days_run == num_days
        })


@app.post(f"{API_PREFIX}/game/start")
def game_start():
    try:
        payload = GameStartRequest(**request.get_json())
    except Exception:
        return err("Invalid request format", 400)
    # Now payload is validated and typed
    session_id = payload.session_id
    if not session_id:
        return err("session_id is required", 400)
    num_days = int(payload.num_days or 5)
    # stop any previous loop
    if session_id in _session_stops:
        _session_stops[session_id].set()
        _session_stops.pop(session_id, None)
    # create and start new loop
    stop_event = threading.Event()
    _session_stops[session_id] = stop_event
    t = threading.Thread(target=_game_loop, args=(session_id, num_days), daemon=True)
    _session_threads[session_id] = t
    t.start()
    # Stats: mark session started
    try:
        user_id = (request.get_json(silent=True) or {}).get('user_id')
        log_session_start(getattr(memory_agent.db_manager, 'db_path', None), session_id, user_id)
    except Exception:
        pass
    return ok({"started": True, "session_id": session_id, "num_days": num_days})


@app.post(f"{API_PREFIX}/game/stop")
def game_stop():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get('session_id')
    if not session_id:
        return err("session_id is required", 400)
    ev = _session_stops.get(session_id)
    if ev:
        ev.set()
        # Stats: mark session stopped
        try:
            user_id = (request.get_json(silent=True) or {}).get('user_id')
            log_session_stop(getattr(memory_agent.db_manager, 'db_path', None), session_id, user_id)
        except Exception:
            pass
        return ok({"stopped": True})
    return ok({"stopped": False})


@app.post(f"{API_PREFIX}/experiments/run_legacy")
def experiments_run():
    """Start one or more self-run experiment sessions in background.

    Body: {"variant_id": str, "num_runs": int, "num_days": int}
    Returns: {"started": true, "sessions": [session_ids...]}
    """
    payload = request.get_json(silent=True) or {}
    variant_id = payload.get('variant_id')
    num_runs = int(payload.get('num_runs') or 1)
    num_days = int(payload.get('num_days') or 2)

    # Load config and set environment variables similarly to /experiments/apply
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), 'experimental_config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        target = None
        for _, exp in (data.get('experiments') or {}).items():
            for v in exp.get('variants', []):
                if v.get('id') == variant_id:
                    target = v
                    break
            if target:
                break
        if not target:
            return err(f"Variant '{variant_id}' not found", 404)

        conf = target.get('config') or {}
        os.environ['AUTO_REPUTATION_UPDATE'] = '1' if conf.get('reputation_enabled', True) else '0'
        agent_map = {}
        for group in ('game_agents', 'social_agents'):
            for k, v in (conf.get(group) or {}).items():
                agent_map[k] = {"provider": v.get('provider'), "model": v.get('model')}
        os.environ['GAME_AGENT_LLM_CONFIGS'] = json.dumps(agent_map)
    except Exception as e:
        return err(f"Failed to apply experiment config: {e}", 500)

    sessions = []
    for i in range(num_runs):
        # Create a new session with experiment metadata
        session = memory_agent.create_session()
        gs = session.game_settings or {}
        gs['experiment'] = {
            'type': 'self',
            'variant_id': variant_id,
            'run_index': i + 1,
        }
        session.game_settings = gs
        try:
            memory_agent.db_manager.update_session(session)
        except Exception:
            pass

        # stop any previous loop for this id (unlikely)
        if session.session_id in _session_stops:
            _session_stops[session.session_id].set()
            _session_stops.pop(session.session_id, None)
        stop_event = threading.Event()
        _session_stops[session.session_id] = stop_event
        t = threading.Thread(target=_game_loop, args=(session.session_id, num_days), daemon=True)
        _session_threads[session.session_id] = t
        t.start()
        sessions.append(session.session_id)

    return ok({"started": True, "sessions": sessions, "num_days": num_days, "variant_id": variant_id})


@app.get(f"{API_PREFIX}/health")
def health():
    return ok({"status": "ok"})


@app.route(f"{API_PREFIX}/player/session/<session_id>", methods=['GET'])
def get_session_info(session_id):
    """Get session information"""
    if session_id not in game_sessions:
        return err("Session not found", 404)
    
    session = game_sessions[session_id]
    return jsonify(session.get_session_info())

@app.route(f"{API_PREFIX}/player/pause", methods=['POST'])
def pause_game():
    """Pause the game"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or session_id not in game_sessions:
        return err("Invalid session", 400)
    
    session = game_sessions[session_id]
    result = session.pause_game()
    
    # Update global game state
    if result['success']:
        game_state['status'] = 'paused'
    
    return jsonify(result)

@app.route(f"{API_PREFIX}/player/resume", methods=['POST'])
def resume_game():
    """Resume the game"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or session_id not in game_sessions:
        return err("Invalid session", 400)
    
    session = game_sessions[session_id]
    result = session.resume_game()
    
    # Update global game state
    if result['success']:
        game_state['status'] = 'running'
    
    return jsonify(result)


@app.route(f"{API_PREFIX}/player/save", methods=['POST'])
def save_game():
    """Save the game"""
    data = request.json
    session_id = data.get('session_id')
    save_type = data.get('type', 'quick')  # quick, auto, manual
    
    if not session_id or session_id not in game_sessions:
        return err("Invalid session", 400)
    
    session = game_sessions[session_id]
    
    if save_type == 'quick':
        result = session.quick_save()
    elif save_type == 'auto':
        result = session.auto_save()
    else:
        result = {
            'success': True,
            'save_point_id': session.create_save_point()['id'],
            'timestamp': datetime.now().isoformat()
        }
    
    return jsonify(result)

@app.route(f"{API_PREFIX}/player/load", methods=['POST'])
def load_game():
    """Load a saved game"""
    data = request.json
    session_id = data.get('session_id')
    save_point_id = data.get('save_point_id')
    
    if not session_id or session_id not in game_sessions:
        return err("Invalid session", 400)
    
    session = game_sessions[session_id]
    success = session.load_save_point(save_point_id)
    
    return jsonify({
        'success': success,
        'message': 'Game loaded' if success else 'Save point not found'
    })

@app.route(f"{API_PREFIX}/player/stats/<session_id>", methods=['GET'])
def get_player_stats(session_id):
    """Get player statistics"""
    if session_id not in game_sessions:
        return err("Session not found", 404)
    
    session = game_sessions[session_id]
    if not session.player:
        return err("No player character", 404)
    
    return jsonify({
        'player': session.player.to_dict(),
        'play_time': session.get_total_play_time(),
        'is_paused': session.is_paused
    })

# -----------------------------------------------------------------------------
# User and session management
# -----------------------------------------------------------------------------
def _init_user_table():
    """Ensure users table exists with TEXT primary key to match DatabaseManager."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Align schema with DatabaseManager (TEXT PK, created_at, metadata)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                metadata TEXT
            )
            """
        )
        conn.commit()
    except Exception as e:
        logger.exception("Failed to initialize users table: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

_init_user_table()

# Track active user sessions
_user_sessions = {}  # {user_id: [session_ids]}
_active_sessions = {}  # {user_id: active_session_id}

@app.route(f"{API_PREFIX}/user/<user_id>/active_session", methods=['POST'])
def set_active_session(user_id: str):
    """Set the active session for a user."""
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    
    try:
        # Verify session exists and belongs to user
        session = memory_agent.db_manager.get_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
            
        # Check if session belongs to user
        exp = (session.game_settings or {}).get('experiment') or {}
        if exp.get('user_id') != user_id:
            return jsonify({"error": "Session does not belong to user"}), 403
        
        # Set as active session
        _active_sessions[user_id] = session_id
        
        # Track in user sessions list if not already
        user_sessions = _user_sessions.setdefault(user_id, [])
        if session_id not in user_sessions:
            if len(user_sessions) >= 7:
                return jsonify({"error": "Maximum sessions reached (7)"}), 400
            user_sessions.append(session_id)
        
        return jsonify({"active_session_id": session_id})
    except Exception as e:
        logger.exception('Failed to set active session: %s', e)
        return jsonify({"error": "Failed to set active session"}), 500

@app.route(f"{API_PREFIX}/user/<user_id>/active_session", methods=['GET'])
def get_active_session(user_id: str):
    """Get the active session for a user."""
    active_session_id = _active_sessions.get(user_id)
    if not active_session_id:
        return jsonify({"error": "No active session"}), 404
    
    return jsonify({"active_session_id": active_session_id})

@app.route(f"{API_PREFIX}/user/<user_id>/reset_sessions", methods=['POST'])
def reset_user_sessions(user_id: str):
    """Reset all sessions and data for a user."""
    try:
        # Clear active session tracking
        if user_id in _active_sessions:
            del _active_sessions[user_id]
        
        # Clear user sessions tracking
        if user_id in _user_sessions:
            del _user_sessions[user_id]
        
        # Clear player chat sessions for user's sessions
        sessions_to_clear = []
        for session_id, npc_map in list(_player_chat_sessions.items()):
            # Check if this session belongs to the user (session ID format: userid_test_x)
            if session_id.startswith(f"{user_id}_test_"):
                sessions_to_clear.append(session_id)
        
        for session_id in sessions_to_clear:
            if session_id in _player_chat_sessions:
                del _player_chat_sessions[session_id]
        
        # Remove user data from database (sessions, metrics, etc.)
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # Enable foreign keys
            cur.execute("PRAGMA foreign_keys = ON")
            
            # Delete user sessions (sessions that start with userid_test_)
            cur.execute("DELETE FROM sessions WHERE session_id LIKE ?", (f"{user_id}_test_%",))
            
            # Delete conversation metrics for user
            cur.execute("DELETE FROM conversation_metrics WHERE user_id = ?", (user_id,))
            
            # Delete UX metrics for user
            cur.execute("DELETE FROM ux_metrics WHERE user_id = ?", (user_id,))
            
            # Delete session checkpoints for user
            cur.execute("DELETE FROM session_checkpoints WHERE user_id = ?", (user_id,))

            # Delete questionnaire responses for user
            try:
                cur.execute("DELETE FROM questionnaire_responses WHERE user_id = ?", (user_id,))
            except Exception as e:
                logger.warning(f"Could not delete questionnaire_responses: {e}")
            
            # Delete other related data
            try:
                # Delete dialogues for user sessions
                cur.execute("""
                    DELETE FROM dialogues 
                    WHERE dialogue_id IN (
                        SELECT dialogue_id FROM dialogues 
                        WHERE session_id LIKE ?
                    )
                """, (f"{user_id}_test_%",))
                
                # Delete messages for user sessions
                cur.execute("""
                    DELETE FROM messages 
                    WHERE session_id LIKE ?
                """, (f"{user_id}_test_%",))
                
                # Delete NPC memories for user sessions
                cur.execute("""
                    DELETE FROM npc_memories 
                    WHERE session_id LIKE ?
                """, (f"{user_id}_test_%",))
                
                # Delete days for user sessions
                try:
                    cur.execute("""
                        DELETE FROM days 
                        WHERE session_id LIKE ?
                    """, (f"{user_id}_test_%",))
                except Exception as e:
                    logger.warning(f"Could not delete days: {e}")
                
                # Delete user events
                try:
                    cur.execute("""
                        DELETE FROM user_events 
                        WHERE user_id = ?
                    """, (user_id,))
                except Exception as e:
                    logger.warning(f"Could not delete user_events: {e}")
                
            except Exception as table_error:
                logger.warning(f"Error cleaning related tables: {table_error}")
            
            conn.commit()
            logger.info(f"Reset all sessions and data for user {user_id}")
            
        except Exception as db_error:
            logger.exception(f"Database error during user reset for {user_id}: %s", db_error)
            # Continue even if DB operations fail
            
        finally:
            try:
                conn.close()
            except Exception:
                pass
        
        return jsonify({"success": True, "message": f"All sessions and data reset for user {user_id}"})
        
    except Exception as e:
        logger.exception(f'Failed to reset sessions for user {user_id}: %s', e)
        return jsonify({"error": "Failed to reset user sessions"}), 500

@app.route(f"{API_PREFIX}/start_session", methods=['POST'])
def start_session():
    """Start or load a session for a user."""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    session_id = data.get('session_id', 'test0')  # Default to test0
    
    # Validate session count (max 7 including test0)
    if len(_user_sessions.get(user_id, [])) >= 7:
        return jsonify({"error": "Maximum sessions reached (7)"}), 400
    
    # Load or create session
    try:
        if not memory_agent.load_session(session_id):
            # Create session using DB-backed settings first, then file fallback
            db_settings = load_settings_from_db('current') or load_settings_from_db('default')
            settings_to_use = db_settings if db_settings is not None else (default_settings or {})
            memory_agent.create_session(session_id=session_id, game_settings=settings_to_use)
            # Ensure NPCs are seeded from DB settings into npc_memories and session.active_npcs
            try:
                _seed_npcs_for_session_from_settings(settings_to_use)
            except Exception:
                pass
        
        # Track user session
        _user_sessions.setdefault(user_id, []).append(session_id)
        _active_sessions[user_id] = session_id
        
        return jsonify({"session_id": session_id})
    except Exception as e:
        logger.exception('Failed to start session: %s', e)
        return jsonify({"error": "failed to start session"}), 500

@app.route(f"{API_PREFIX}/sessions/<session_id>/npcs", methods=['GET'])
def get_session_npcs(session_id):
    """Get NPCs for a specific session (DB-sourced, independent of active_npcs).

    Primary source: npc_memories with character_properties. Fallback: names from dialogues.
    """
    try:
        # Ensure the session exists
        sess = memory_agent.db_manager.get_session(session_id)
        if not sess:
            return err("Session not found", 404)

        results = []
        # Prefer npc_memories entries which include character properties
        try:
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT npc_name, character_properties FROM npc_memories WHERE session_id = ?",
                    (session_id,),
                )
                rows = cur.fetchall() or []
                if rows:
                    for r in rows:
                        try:
                            props = json.loads(r[1]) if r[1] else {}
                        except Exception:
                            props = {}
                        results.append({
                            'name': r[0],
                            'role': props.get('role'),
                            'story': props.get('story'),
                            'personality': props.get('personality') if isinstance(props, dict) else None,
                            'locations': props.get('locations') if isinstance(props, dict) else None,
                        })
                if not results:
                    # Fallback to distinct names from dialogues
                    cur.execute("SELECT DISTINCT initiator FROM dialogues WHERE session_id = ?", (session_id,))
                    names_i = [r[0] for r in cur.fetchall() if r and r[0]]
                    cur.execute("SELECT DISTINCT receiver FROM dialogues WHERE session_id = ?", (session_id,))
                    names_r = [r[0] for r in cur.fetchall() if r and r[0]]
                    for n in sorted(set(names_i + names_r)):
                        results.append({'name': n})
        except Exception:
            # As a last resort, derive from MemoryAgent utilities
            try:
                if memory_agent.load_session(session_id):
                    for nm in (memory_agent.get_all_npc_names() or []):
                        results.append({'name': nm})
            except Exception:
                pass

        return ok({'npcs': results})
    except Exception as e:
        logger.exception("Failed to get session NPCs: %s", e)
        return err("Failed to get NPCs", 500)

@app.route(f"{API_PREFIX}/sessions/<session_id>/npcs", methods=['POST'])
def add_session_npcs(session_id):
    """Add NPCs to a specific session"""
    try:
        data = request.get_json(silent=True) or {}
        npcs_to_add = data.get('npcs', [])
        
        if not npcs_to_add:
            return err("No NPCs provided", 400)
            
        # Load the session
        if not memory_agent.load_session(session_id):
            return err("Session not found", 404)
            
        session = memory_agent.current_session
        
        # Add NPCs to session's active_npcs list
        current_npcs = set(session.active_npcs)
        added_npcs = []
        
        for npc_data in npcs_to_add:
            npc_name = npc_data.get('name')
            if not npc_name:
                continue
                
            if npc_name not in current_npcs:
                session.active_npcs.append(npc_name)
                current_npcs.add(npc_name)
                added_npcs.append(npc_name)
                
                # Create NPC memory with provided character properties
                npc_memory = memory_agent.get_npc_memory(npc_name)
                if not npc_memory:
                    # Create new NPC memory with character properties
                    character_properties = {
                        'name': npc_name,
                        'role': npc_data.get('role', 'Unknown'),
                        'story': npc_data.get('story', ''),
                        'personality': npc_data.get('personality', ''),
                        'locations': npc_data.get('locations', {}),
                        'type': 'npc'
                    }
                    
                    from agents.dataclasses import NPCMemory
                    from datetime import datetime
                    new_npc_memory = NPCMemory(
                        npc_name=npc_name,
                        session_id=session_id,
                        character_properties=character_properties,
                        created_at=datetime.now(),
                        last_updated=datetime.now()
                    )
                    memory_agent.db_manager.create_or_update_npc_memory(new_npc_memory)
        
        # Update session in database
        memory_agent.db_manager.update_session(session)
        
        return ok({
            "added_npcs": added_npcs,
            "total_npcs": len(session.active_npcs)
        })
        
    except Exception as e:
        logger.exception("Failed to add NPCs to session: %s", e)
        return err("Failed to add NPCs", 500)

@app.route(f"{API_PREFIX}/verify_consistency", methods=['POST'])
def verify_consistency():
    """Verify frontend-backend data consistency."""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    session_id = data.get('session_id')
    
    try:
        # Verify session belongs to user
        if session_id not in _user_sessions.get(user_id, []):
            return err("Session does not belong to user", 400)
            
        # Verify active session matches
        if _active_sessions.get(user_id) != session_id:
            return err("Active session mismatch", 400)
            
        # Verify NPC data consistency
        if not memory_agent.load_session(session_id):
            return err("Failed to load session", 400)
            
        session = memory_agent.current_session
        npcs = memory_agent.get_active_npcs()
        
        return ok({
            "consistent": True,
            "active_npcs": npcs,
            "session_day": session.current_day
        })
        
    except Exception as e:
        logger.exception("Consistency check failed: %s", e)
        return err("Consistency check failed", 500)

# -----------------------------------------------------------------------------
# Global preflight handler for CORS (ensures 200 on any /api/* OPTIONS)
# -----------------------------------------------------------------------------
@app.before_request
def _handle_cors_preflight():
    if request.method == 'OPTIONS' and request.path.startswith(API_PREFIX):
        resp = app.make_default_options_response()
        h = resp.headers
        origin = request.headers.get('Origin', 'http://localhost:5173')
        # Align with configured origin
        h['Access-Control-Allow-Origin'] = origin if origin == 'http://localhost:5173' else 'http://localhost:5173'
        h.add('Vary', 'Origin')
        # Mirror requested headers if provided
        req_headers = request.headers.get('Access-Control-Request-Headers')
        h['Access-Control-Allow-Headers'] = req_headers or 'Content-Type, Authorization'
        h['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        h['Access-Control-Max-Age'] = '86400'
        return resp

if __name__ == '__main__':
    # Database is initialized by MemoryAgent/DatabaseManager
    # Run with SocketIO support
    port = int(os.environ.get('API_PORT', '8000'))
    socketio.run(app, debug=True, port=port)

# -----------------------------------------------------------------------------
# Config API: update runtime settings without environment variables
# -----------------------------------------------------------------------------
@app.post(f"{API_PREFIX}/config/update")
def update_runtime_config():
    data = request.json or {}
    # Toggle SSE runtime behavior
    if 'sse_enabled' in data:
        sse_on = bool(data['sse_enabled'])
        app_runtime_config['sse_enabled'] = sse_on
        try:
            if sse_on:
                # Register SSE bridge listener if turning on
                memory_agent.add_event_listener(_on_memory_signal)
            else:
                # Remove if turning off
                memory_agent.remove_event_listener(_on_memory_signal)
        except Exception:
            pass
    # Update reputation settings
    if 'reputation_auto_update' in data:
        app_runtime_config['reputation_auto_update'] = bool(data['reputation_auto_update'])
    if 'reputation_update_timeout' in data:
        try:
            app_runtime_config['reputation_update_timeout'] = float(data['reputation_update_timeout'])
        except Exception:
            return err("Invalid reputation_update_timeout", 400)

    # Update social agent LLM configs (Opinion/Stance/Knowledge/Reputation)
    social_llms = data.get('social_agent_llms')
    if isinstance(social_llms, dict):
        app_runtime_config['social_agent_llms'] = social_llms
        # Apply to live agents
        def _apply(agent_attr: str, key: str):
            cfg = social_llms.get(key) or {}
            prov = cfg.get('provider')
            model = cfg.get('model')
            agent = getattr(social_service, agent_attr, None)
            if agent and hasattr(agent, 'set_llm_provider') and (prov or model):
                agent.set_llm_provider(prov or 'test', model or 'test')
        _apply('_opinion', 'opinion_agent')
        _apply('_stance', 'stance_agent')
        _apply('_knowledge', 'knowledge_agent')
        _apply('_reputation', 'reputation_agent')

    # Update game agent LLM configs used by GameLoopManager
    game_llms = data.get('game_agent_llms')
    if isinstance(game_llms, dict):
        app_runtime_config['game_agent_llms'] = game_llms

    # Optional: summary LLM for background memory/session summarization
    summary_llm = data.get('memory_summary_llm')
    if isinstance(summary_llm, dict):
        prov = summary_llm.get('provider')
        model = summary_llm.get('model')
        try:
            memory_agent.set_memory_summary_llm(prov, model)
        except Exception as e:
            logger.warning("Failed to set memory summary LLM: %s", e)

    # Ensure reputation listener reflects latest config
    _update_reputation_listener()

    return ok({
        'success': True,
        'config': app_runtime_config
    })

# -----------------------------------------------------------------------------
# Experiments API: trigger experiments from the backend (no envs)
# -----------------------------------------------------------------------------
@app.post(f"{API_PREFIX}/experiments/run")
def run_experiment_api():
    data = request.json or {}
    experiment = data.get('experiment')
    config_path = data.get('config_path', 'experimental_config.json')
    if not experiment:
        return err("Missing 'experiment'", 400)
    try:
        from runner import run_experiment_from_app
        result = run_experiment_from_app(experiment, config_path)
        return ok(result)
    except Exception as e:
        logger.exception("Experiment run failed: %s", e)
        return err(str(e), 500)

# -----------------------------------------------------------------------------
# Avatars API
# -----------------------------------------------------------------------------
@app.post(f"{API_PREFIX}/avatars/generate")
def generate_avatar():
    """Generate (or retrieve cached) NPC avatar and attach to session.

    Body: { session_id: str, npc_name: str, force?: bool }
    Returns: { portrait_url }
    """
    payload = request.get_json(silent=True) or {}
    session_id = (payload.get('session_id') or '').strip()
    npc_name = (payload.get('npc_name') or '').strip()
    force = bool(payload.get('force'))
    if not session_id or not npc_name:
        return err('session_id and npc_name are required', 400)

    # Load session
    if not memory_agent.load_session(session_id):
        return err('session not found', 404)
    session = memory_agent.current_session

    # Compute static path and URL
    backend_dir = os.path.dirname(__file__)
    safe_name = ''.join([c if c.isalnum() or c in ['-','_'] else '_' for c in npc_name])
    static_dir = os.path.join(backend_dir, 'static', 'avatars', session_id)
    fname = f"{safe_name}.png"
    fpath = os.path.join(static_dir, fname)
    url = f"/static/avatars/{session_id}/{fname}"

    # If exists and not forcing, return
    try:
        if os.path.exists(fpath) and not force:
            try:
                _attach_portrait_url_to_session(npc_name, url)
            except Exception:
                pass
            return ok({'portrait_url': url})
    except Exception:
        pass

    # Ensure provider configured
    provider = AvatarProvider(os.environ.get('AVATAR_PROVIDER'))
    if not provider.is_configured():
        return err('Avatar provider not configured. Set AVATAR_PROVIDER and its API key(s).', 400)

    # Build prompt from NPC and world
    try:
        props = memory_agent.get_character_properties(npc_name) or {'name': npc_name}
        props['name'] = npc_name
    except Exception:
        props = {'name': npc_name}
    world = memory_agent.get_world() or {}
    prompt = build_avatar_prompt(props, world)

    # Generate and save
    try:
        img_bytes = provider.generate_png_bytes(prompt)
        os.makedirs(static_dir, exist_ok=True)
        with open(fpath, 'wb') as f:
            f.write(img_bytes)
    except Exception as e:
        logger.exception('Avatar generation failed: %s', e)
        return err('Avatar generation failed', 500)

    # Attach to session character_list
    try:
        _attach_portrait_url_to_session(npc_name, url)
    except Exception as e:
        logger.warning('Failed to persist portrait_url: %s', e)

    return ok({'portrait_url': url})


def _attach_portrait_url_to_session(npc_name: str, portrait_url: str) -> None:
    """Update current session's character_list entry with portrait_url and persist."""
    sess = memory_agent.current_session
    if not sess:
        return
    gs = sess.game_settings or {}
    cl = gs.get('character_list') or []
    updated = False
    for c in cl:
        if isinstance(c, dict) and c.get('name') == npc_name:
            if c.get('portrait_url') != portrait_url:
                c['portrait_url'] = portrait_url
                updated = True
            break
    else:
        cl.append({'name': npc_name, 'type': 'npc', 'life_cycle': 'active', 'portrait_url': portrait_url})
        updated = True
    if updated or gs.get('character_list') is None:
        gs['character_list'] = cl
        sess.game_settings = gs
        try:
            memory_agent.db_manager.update_session(sess)
        except Exception:
            pass
