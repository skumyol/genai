import os
import json
from datetime import datetime
from typing import Any, Callable, Dict

from flask import Blueprint, jsonify, request
from agents.dataclasses import TimePeriod
from user_dataset_manager import init_user_dataset, switch_memory_agent_to_user, get_user_db_path
import traceback


def create_deferred_blueprint(
    *,
    api_prefix: str,
    memory_agent: Any,
    social_service: Any,
    get_db: Callable[[], Any],
    ok: Callable[[Any], Any],
    err: Callable[[str, int], Any],
    default_settings_path: str,
    default_settings: Dict[str, Any],
    game_sessions: Dict[str, Any],
) -> Blueprint:
    """Create a blueprint with deferred routes that are independent of the game loop.

    These routes are extracted from app.py and can be registered in the future when needed.
    Dependencies are injected to avoid circular imports and tight coupling.
    """
    bp = Blueprint("deferred", __name__)

    # Ensure questionnaire_responses table exists (TEXT user_id to match frontend IDs like 'user3')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS questionnaire_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT,
                questionnaire_id TEXT NOT NULL,
                phase TEXT,
                responses_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    except Exception:
        pass

    # Note: Per-user dataset endpoints have been removed (centralized DB in use).

    @bp.get(f"{api_prefix}/user/stats")
    def api_user_stats():
        try:
            from user_stats_manager import read_stats as _read_stats, group_by_checkpoint as _group
            db_path = getattr(memory_agent.db_manager, 'db_path', None)
            stats = _read_stats(db_path)
            # Include grouped view for UI convenience
            try:
                stats['by_checkpoint'] = _group(stats, db_path)
            except Exception:
                stats['by_checkpoint'] = {}
            return jsonify(stats)
        except Exception as e:
            return jsonify({"error": f"Failed to read stats: {e}"}), 500

    @bp.get(f"{api_prefix}/user/stats_csv")
    def api_user_stats_csv():
        try:
            from user_stats_manager import read_stats as _read_stats, generate_csv as _csv
            view = request.args.get('view', 'session')
            db_path = getattr(memory_agent.db_manager, 'db_path', None)
            stats = _read_stats(db_path)
            content = _csv(stats, view=view if view in ('session','checkpoint') else 'session', db_path=db_path)
            from flask import Response
            resp = Response(content, mimetype='text/csv')
            filename = f"user_stats_{view}.csv"
            resp.headers['Content-Disposition'] = f"attachment; filename={filename}"
            return resp
        except Exception as e:
            return jsonify({"error": f"Failed to export stats: {e}"}), 500

    # ---------------------------------------------------------------------
    # Admin: DB info (paths and table counts)
    # ---------------------------------------------------------------------
    @bp.get(f"{api_prefix}/admin/db_info")
    def admin_db_info():
        try:
            from app import get_checkpoint_db_path
            paths = {
                'main': getattr(memory_agent.db_manager, 'db_path', None),
                'checkpoints': get_checkpoint_db_path(),
            }
            counts = {}
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                for table in ("sessions", "days", "dialogues", "messages", "npc_memories", "session_metrics", "user_events", "session_imports"):
                    try:
                        cur.execute(f"SELECT COUNT(1) FROM {table}")
                        counts[table] = cur.fetchone()[0]
                    except Exception:
                        counts[table] = None
            return jsonify({'paths': paths, 'counts': counts})
        except Exception as e:
            return jsonify({"error": f"Failed to get DB info: {e}"}), 500

    # ---------------------------------------------------------------------
    # Admin: Vacuum/Analyze database
    # ---------------------------------------------------------------------
    @bp.post(f"{api_prefix}/admin/db_maint")
    def admin_db_maint():
        try:
            import sqlite3 as _sqlite3
            from app import get_checkpoint_db_path as _get_ckpt
            data = request.get_json(silent=True) or {}
            target = (data.get('target') or 'main').lower()  # 'main' or 'checkpoints'
            if target == 'checkpoints':
                path = _get_ckpt()
                conn = _sqlite3.connect(path)
            else:
                path = getattr(memory_agent.db_manager, 'db_path', None)
                conn = _sqlite3.connect(path)
            conn.execute("VACUUM")
            try:
                conn.execute("ANALYZE")
            except Exception:
                pass
            conn.close()
            return jsonify({"ok": True, "target": target, "path": path})
        except Exception as e:
            return jsonify({"error": f"Failed DB maintenance: {e}"}), 500

    # ---------------------------------------------------------------------
    # Experiments: import frozen checkpoint into an existing user session
    # ---------------------------------------------------------------------
    @bp.post(f"{api_prefix}/experiments/import_into_session")
    def import_into_session():
        """Deep-copy a frozen checkpoint session from base DB into a target session in the user DB.

        Body: { source_session_id, target_session_id, user_id?, experiment_no? }
        """
        data = request.get_json(silent=True) or {}
        src_id = data.get('source_session_id')
        tgt_id = data.get('target_session_id')
        user_id = data.get('user_id')
        exp_no = data.get('experiment_no')
        if not src_id or not tgt_id:
            return jsonify({"error": "source_session_id and target_session_id are required"}), 400

        try:
            # Optionally ensure user's dataset is selected
            if user_id:
                switch_memory_agent_to_user(memory_agent, str(user_id))

            # Read from base DB
            base_db = os.path.join(os.path.dirname(__file__), 'databases', 'checkpoints.db')
            import sqlite3
            src_conn = sqlite3.connect(base_db)
            src_conn.row_factory = sqlite3.Row

            # Wipe target content and recreate target session row minimally
            memory_agent.db_manager.delete_session_data(tgt_id)
            tgt_session = memory_agent.create_session(session_id=tgt_id)

            # Pull source session meta
            cur = src_conn.cursor()
            cur.execute("SELECT * FROM sessions WHERE session_id = ?", (src_id,))
            srow = cur.fetchone()
            if not srow:
                return jsonify({"error": "Source session not found"}), 404

            # Copy days (preserve all fields) according to maingamedata schema
            # Note: maingamedata 'days' table uses (session_id, day) as PK and has no 'day_id' column
            cur.execute("SELECT * FROM days WHERE session_id = ? ORDER BY day, time_period", (src_id,))
            day_rows = cur.fetchall()
            for d in day_rows:
                try:
                    with memory_agent.db_manager.get_connection() as tgt_conn:
                        tcur = tgt_conn.cursor()
                        tcur.execute(
                            """
                            INSERT OR REPLACE INTO days
                            (session_id, day, time_period, started_at, ended_at, dialogue_ids, metadata, active_npcs, day_summary, passive_npcs)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                tgt_id,
                                d["day"],
                                d["time_period"],
                                d["started_at"],
                                d["ended_at"],
                                d["dialogue_ids"],
                                d["metadata"],
                                d["active_npcs"],
                                d.get("day_summary"),
                                # Some older DBs may not have passive_npcs; handle via key check
                                (d["passive_npcs"] if "passive_npcs" in d.keys() else json.dumps([])),
                            )
                        )
                        tgt_conn.commit()
                except Exception:
                    continue

            # Copy dialogues and messages preserving IDs
            # Insert dialogues
            cur.execute("SELECT * FROM dialogues WHERE session_id = ? ORDER BY started_at", (src_id,))
            dlg_rows = cur.fetchall()
            with memory_agent.db_manager.get_connection() as tgt_conn:
                tcur = tgt_conn.cursor()
                import json as _json
                for d in dlg_rows:
                    try:
                        tcur.execute(
                            """
                            INSERT OR REPLACE INTO dialogues
                            (dialogue_id, session_id, initiator, receiver, day, location, time_period, started_at, ended_at, message_ids, summary, summary_length, total_text_length)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                d["dialogue_id"], tgt_id, d["initiator"], d["receiver"], d["day"], d["location"], d["time_period"], d["started_at"], d["ended_at"], d["message_ids"], d["summary"], d["summary_length"], d["total_text_length"],
                            )
                        )
                    except Exception:
                        pass
                # Insert messages
                cur.execute("SELECT m.* FROM messages m JOIN dialogues d ON m.dialogue_id=d.dialogue_id WHERE d.session_id=? ORDER BY m.timestamp", (src_id,))
                msg_rows = cur.fetchall()
                for m in msg_rows:
                    try:
                        tcur.execute(
                            """
                            INSERT OR REPLACE INTO messages
                            (message_id, dialogue_id, sender, receiver, message_text, timestamp, sender_opinion, receiver_opinion)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                m["message_id"], m["dialogue_id"], m["sender"], m["receiver"], m["message_text"], m["timestamp"], m["sender_opinion"], m["receiver_opinion"],
                            )
                        )
                    except Exception:
                        pass
                # Copy npc_memories
                cur.execute("SELECT * FROM npc_memories WHERE session_id=?", (src_id,))
                mem_rows = cur.fetchall()
                for r in mem_rows:
                    try:
                        # character_properties may not exist in older DBs
                        char_props = None
                        try:
                            if 'character_properties' in r.keys():
                                char_props = r["character_properties"]
                        except Exception:
                            char_props = None
                        tcur.execute(
                            """
                            INSERT OR REPLACE INTO npc_memories
                            (npc_name, session_id, dialogue_ids, messages_summary, messages_summary_length, created_at, last_updated, last_summarized, opinion_on_npcs, world_knowledge, social_stance, character_properties)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                r["npc_name"], tgt_id, r["dialogue_ids"], r["messages_summary"], r["messages_summary_length"], r["created_at"], r["last_updated"], r["last_summarized"], r["opinion_on_npcs"], r["world_knowledge"], r["social_stance"], char_props,
                            )
                        )
                    except Exception:
                        pass
                tgt_conn.commit()

            # Update target session metadata to reflect experiment linkage, copy source fields
            try:
                import json as _json
                # Start from source session row values
                try:
                    game_settings = _json.loads(srow["game_settings"] or '{}')
                except Exception:
                    game_settings = {}
                agent_settings = srow["agent_settings"] if "agent_settings" in srow.keys() else None
                reputations = srow["reputations"] if "reputations" in srow.keys() else None
                session_summary = srow["session_summary"] if "session_summary" in srow.keys() else None
                active_npcs = srow["active_npcs"] if "active_npcs" in srow.keys() else None
                dialogue_ids = srow["dialogue_ids"] if "dialogue_ids" in srow.keys() else None

                # Merge experiment metadata for user study
                src_exp = (game_settings.get('experiment') or {}) if isinstance(game_settings, dict) else {}
                game_settings = game_settings if isinstance(game_settings, dict) else {}
                game_settings['experiment'] = {
                    'type': 'user',
                    'user_id': user_id,
                    'experiment_no': exp_no,
                    'scenario_source_session_id': src_id,
                    'experiment_name': src_exp.get('experiment_name'),
                    'variant_id': src_exp.get('variant_id'),
                }

                # Persist via direct UPDATE/INSERT matching maingamedata schema
                with memory_agent.db_manager.get_connection() as tgt_conn:
                    tcur = tgt_conn.cursor()
                    tcur.execute(
                        """
                        INSERT OR REPLACE INTO sessions
                        (session_id, created_at, last_updated, current_day, current_time_period, game_settings, agent_settings, reputations, session_summary, active_npcs, dialogue_ids)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tgt_id,
                            srow["created_at"],
                            datetime.utcnow().isoformat(),
                            srow["current_day"],
                            srow["current_time_period"],
                            _json.dumps(game_settings),
                            agent_settings,
                            reputations,
                            session_summary,
                            active_npcs,
                            dialogue_ids,
                        )
                    )
                    tgt_conn.commit()
            except Exception:
                pass

            # Update ID counters to prevent conflicts with imported data
            try:
                with memory_agent.db_manager.get_connection() as tgt_conn:
                    tcur = tgt_conn.cursor()
                    
                    # Find highest message_id in the target database
                    tcur.execute("SELECT MAX(CAST(message_id AS INTEGER)) FROM messages WHERE message_id GLOB '[0-9]*'")
                    max_msg_row = tcur.fetchone()
                    max_message_id = int(max_msg_row[0]) if max_msg_row and max_msg_row[0] is not None else -1
                    
                    # Update the messages ID counter to be higher than the highest imported ID
                    next_message_id = max_message_id + 1
                    tcur.execute("""
                        INSERT OR REPLACE INTO id_counters (entity, next_id) 
                        VALUES ('messages', ?)
                    """, (next_message_id,))
                    
                    # Also update dialogue ID counter if needed
                    tcur.execute("SELECT COUNT(*) FROM dialogues")
                    dialogue_count_row = tcur.fetchone()
                    dialogue_count = int(dialogue_count_row[0]) if dialogue_count_row else 0
                    tcur.execute("""
                        INSERT OR REPLACE INTO id_counters (entity, next_id) 
                        VALUES ('dialogues', ?)
                    """, (dialogue_count,))
                    
                    tgt_conn.commit()
            except Exception as e:
                # Log but don't fail the import
                print(f"Warning: Failed to update ID counters after import: {e}")

            # Stats: record import
            try:
                from user_stats_manager import log_import as _log_import
                _log_import(getattr(memory_agent.db_manager, 'db_path', None), tgt_id, src_id)
            except Exception:
                pass

            return jsonify({
                'ok': True,
                'target_session_id': tgt_id,
                'source_session_id': src_id,
            })
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": f"Import failed: {e}"}), 500
        finally:
            try:
                src_conn.close()
            except Exception:
                pass


    # ---------------------------------------------------------------------
    # Admin: Reinitialize database (dangerous; clears all sessions and data)
    # ---------------------------------------------------------------------
    @bp.post(f"{api_prefix}/admin/reinit_db")
    def admin_reinit_db():
        """Clear all tables related to gameplay/session data.

        This deletes rows from messages, dialogues, days, npc_memories, sessions.
        Intended for development to remove noisy historical data.
        """
        try:
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                counts = {}
                for table in ("messages", "dialogues", "days", "npc_memories", "sessions"):
                    try:
                        cur.execute(f"SELECT COUNT(1) FROM {table}")
                        counts[f"{table}_before"] = cur.fetchone()[0]
                    except Exception:
                        counts[f"{table}_before"] = None
                # Delete in safe order
                cur.execute("DELETE FROM messages")
                cur.execute("DELETE FROM dialogues")
                cur.execute("DELETE FROM days")
                cur.execute("DELETE FROM npc_memories")
                cur.execute("DELETE FROM sessions")
                conn.commit()
                try:
                    cur.execute("VACUUM")
                except Exception:
                    pass
                for table in ("messages", "dialogues", "days", "npc_memories", "sessions"):
                    try:
                        cur.execute(f"SELECT COUNT(1) FROM {table}")
                        counts[f"{table}_after"] = cur.fetchone()[0]
                    except Exception:
                        counts[f"{table}_after"] = None
            return ok({"reinitialized": True, "counts": counts})
        except Exception as e:
            return err(f"Failed to reinitialize DB: {e}", 500)

    # ---------------------------------------------------------------------
    # Users (incremental ids: user1..userN) and dataset info
    # ---------------------------------------------------------------------
    @bp.post(f"{api_prefix}/users")
    def create_user_stub():
        """Generate and return an incremental user_id (userN) and ensure dataset + DB rows exist.

        Also seeds main_game_data for this user so analytics are initialized.
        """
        try:
            users_root = os.path.join(os.path.dirname(__file__), 'users')
            os.makedirs(users_root, exist_ok=True)
            max_n = 0
            for name in os.listdir(users_root):
                if not name.startswith('user'):
                    continue
                suffix = name[4:]
                if suffix.isdigit():
                    max_n = max(max_n, int(suffix))
            new_id = f"user{max_n + 1}"

            # Ensure per-user directory (legacy no-op)
            try:
                init_user_dataset(new_id)
            except Exception:
                pass

            # Ensure DB 'users' row exists and seed main_game_data for this user
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR IGNORE INTO users (user_id, created_at, metadata) VALUES (?, ?, ?)",
                    (new_id, datetime.utcnow().isoformat(), json.dumps({})),
                )
                conn.commit()
            except Exception:
                # best-effort; do not fail user creation
                pass

            try:
                # Seed top-level game data row so downstream queries see the user
                if not memory_agent.db_manager.get_main_game_data(new_id):
                    memory_agent.db_manager.create_main_game_data(user_id=new_id)
            except Exception:
                pass

            return jsonify({"user_id": new_id})
        except Exception as e:
            return jsonify({"error": f"Failed to create user id: {e}"}), 500

    # ---------------------------------------------------------------------
    # Memory API endpoints
    # ---------------------------------------------------------------------
    @bp.route(f"{api_prefix}/memory/session", methods=["POST"])
    def create_memory_session():
        data = request.json or {}
        session_id = data.get("session_id")
        session = memory_agent.create_session(session_id)
        return jsonify(
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "current_day": session.current_day,
                "current_time_period": session.current_time_period.value,
            }
        )

    @bp.route(f"{api_prefix}/memory/dialogue", methods=["POST"])
    def start_dialogue():
        data = request.json or {}
        initiator = data.get("initiator")
        receiver = data.get("receiver")
        if not initiator or not receiver:
            return jsonify({"error": "Missing initiator or receiver"}), 400
        dialogue = memory_agent.start_dialogue(initiator, receiver)
        return jsonify(
            {
                "dialogue_id": dialogue.dialogue_id,
                "initiator": dialogue.initiator,
                "receiver": dialogue.receiver,
                "started_at": dialogue.started_at.isoformat(),
            }
        )

    @bp.route(f"{api_prefix}/memory/message", methods=["POST"])
    def add_message():
        data = request.json or {}
        dialogue_id = data.get("dialogue_id")
        sender = data.get("sender")
        receiver = data.get("receiver")
        message_text = data.get("message_text")
        sender_opinion = data.get("sender_opinion")
        if not all([dialogue_id, sender, receiver, message_text]):
            return jsonify({"error": "Missing required fields"}), 400
        try:
            message = memory_agent.add_message(
                dialogue_id, sender, receiver, message_text, sender_opinion
            )
            return jsonify(
                {
                    "message_id": message.message_id,
                    "timestamp": message.timestamp.isoformat(),
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "message_text": message.message_text,
                    "sender_opinion": message.sender_opinion,
                }
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @bp.route(f"{api_prefix}/memory/dialogue/<dialogue_id>/end", methods=["POST"])
    def end_dialogue(dialogue_id):
        data = request.json or {}
        summary = data.get("summary", "")
        try:
            dialogue = memory_agent.end_dialogue(dialogue_id, summary)
            return jsonify(
                {
                    "dialogue_id": dialogue.dialogue_id,
                    "ended_at": dialogue.ended_at.isoformat(),
                    "summary": dialogue.summary,
                }
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @bp.route(f"{api_prefix}/memory/npc/<npc_id>", methods=["GET"])
    def get_npc_memory(npc_id):
        memories = memory_agent.get_npc_memories(npc_id, limit=10)
        return jsonify(
            {
                "npc_id": npc_id,
                "memories": [
                    {
                        "memory_id": memory.memory_id,
                        "content": memory.content,
                        "opinion": memory.opinion,
                        "created_at": memory.created_at.isoformat(),
                        "last_updated": memory.last_updated.isoformat(),
                    }
                    for memory in memories
                ],
            }
        )

    @bp.route(f"{api_prefix}/memory/npc/<npc_id>/context", methods=["GET"])
    def get_npc_context(npc_id):
        context = memory_agent.get_npc_context(npc_id)
        return jsonify({"npc_id": npc_id, "context": context})

    @bp.route(f"{api_prefix}/memory/session/<session_id>", methods=["GET"])
    def get_session_data(session_id):
        session = memory_agent.get_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        return jsonify(
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_updated": session.last_updated.isoformat(),
                "current_day": session.current_day,
                "current_time_period": session.current_time_period.value,
                "session_summary": session.session_summary,
                "active_npcs": session.active_npcs,
            }
        )

    @bp.route(f"{api_prefix}/memory/npc/<npc_id>/update", methods=["POST"])
    def update_npc_memory(npc_id):
        data = request.json or {}
        content = data.get("content")
        opinion = data.get("opinion", "")
        if not content:
            return jsonify({"error": "Missing content"}), 400
        memory = memory_agent.update_npc_memory(npc_id, content, opinion)
        return jsonify(
            {
                "memory_id": memory.memory_id,
                "npc_id": memory.npc_id,
                "content": memory.content,
                "opinion": memory.opinion,
                "created_at": memory.created_at.isoformat(),
                "last_updated": memory.last_updated.isoformat(),
            }
        )

    @bp.route(f"{api_prefix}/memory/time/advance", methods=["POST"])
    def advance_time():
        data = request.json or {}
        new_day = data.get("new_day")
        new_time_period = data.get("new_time_period")
        memory_agent.advance_time(new_day, new_time_period)
        return jsonify(
            {
                "current_day": memory_agent.current_session.current_day,
                "current_time_period": memory_agent.current_session.current_time_period.value,
                "last_updated": memory_agent.current_session.last_updated.isoformat(),
            }
        )

    # ---------------------------------------------------------------------
    # Game Session Management
    # ---------------------------------------------------------------------
    @bp.route(f"{api_prefix}/game/session", methods=["POST"])
    def create_game_session():
        data = request.json or {}
        session_id = data.get("session_id")
        if not default_settings:
            return jsonify({"error": "Default settings not loaded"}), 500
        memory_session = memory_agent.create_session(session_id)
        npc_list = []
        if "npc_templates" in default_settings:
            for npc_template in default_settings["npc_templates"]:
                npc_list.append(npc_template["name"])
                existing_memories = memory_agent.get_npc_memories(
                    npc_template["name"], limit=1
                )
                if not existing_memories:
                    background_text = (
                        f"Background: {npc_template.get('story', 'No background available.')}\n"
                    )
                    background_text += f"Role: {npc_template.get('role', 'Unknown')}\n"
                    background_text += (
                        f"Personality: {npc_template.get('personality', {})}\n"
                    )
                    background_text += f"Skills: {npc_template.get('skills', {})}\n"
                    memory_agent.update_npc_memory(
                        npc_template["name"],
                        background_text,
                        "This is my background and initial setup.",
                    )
        game_sessions[memory_session.session_id] = {
            "memory_session": memory_session,
            "npc_list": npc_list,
            "settings": default_settings,
            "created_at": datetime.now(),
        }
        return jsonify(
            {
                "session_id": memory_session.session_id,
                "created_at": memory_session.created_at.isoformat(),
                "current_day": memory_session.current_day,
                "current_time_period": memory_session.current_time_period.value,
                "npcs_initialized": len(npc_list),
                "npc_list": npc_list,
                "world_name": default_settings.get("world", {}).get(
                    "name", "Unknown"
                ),
            }
        )

    @bp.route(f"{api_prefix}/game/session/<session_id>", methods=["GET"])
    def get_game_session(session_id):
        if session_id not in game_sessions:
            return jsonify({"error": "Session not found"}), 404
        session_data = game_sessions[session_id]
        memory_session = session_data["memory_session"]
        return jsonify(
            {
                "session_id": session_id,
                "current_day": memory_session.current_day,
                "current_time_period": memory_session.current_time_period.value,
                "npc_list": session_data["npc_list"],
                "active_dialogues": [],
                "world_name": session_data["settings"].get("world", {}).get(
                    "name", "Unknown"
                ),
                "created_at": session_data["created_at"].isoformat(),
            }
        )

    # ---------------------------------------------------------------------
    # Sessions API (alias routes for frontend expectations)
    # ---------------------------------------------------------------------
    @bp.get(f"{api_prefix}/sessions")
    def list_sessions_alias():
        """List sessions with optional experiment filters (minimally invasive).

        Accepts: user_id, experiment_no, exp_type
        """
        q_user = request.args.get("user_id")
        q_exp_no = request.args.get("experiment_no")
        q_exp_type = request.args.get("exp_type")  # 'self' | 'user'
        q_role = request.args.get("role")  # 'admin' to allow all sessions
        q_exp_name = request.args.get("experiment_name")
        q_variant_id = request.args.get("variant_id")
        # Default: for non-admin, show only experimental 'self' sessions
        if not q_role == 'admin' and not q_exp_type:
            q_exp_type = 'self'
        sessions = []
        try:
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT session_id, created_at, last_updated, current_day, current_time_period, session_summary, active_npcs, game_settings FROM sessions ORDER BY created_at DESC"
                )
                for row in cur.fetchall():
                    try:
                        gs = json.loads(row["game_settings"] or '{}')
                    except Exception:
                        gs = {}
                    exp = gs.get('experiment') or {}
                    # If not admin and no experiment metadata, hide from users
                    if q_role != 'admin' and not exp:
                        continue
                    # Filters if provided
                    if q_user and str(exp.get('user_id')) != str(q_user):
                        continue
                    if q_exp_no and str(exp.get('experiment_no')) != str(q_exp_no):
                        continue
                    if q_exp_type and str(exp.get('type')) != str(q_exp_type):
                        continue
                    if q_exp_name and str(exp.get('experiment_name')) != str(q_exp_name):
                        continue
                    if q_variant_id and str(exp.get('variant_id')) != str(q_variant_id):
                        continue
                    sessions.append({
                        "session_id": row["session_id"],
                        "created_at": row["created_at"],
                        "last_updated": row["last_updated"],
                        "current_day": row["current_day"],
                        "current_time_period": row["current_time_period"],
                        "session_summary": row["session_summary"] or "",
                        "active_npcs": json.loads(row["active_npcs"] or "[]"),
                        "experiment": exp,
                    })
            # Assign a simple display index starting from 1 (oldest -> newest)
            for idx, item in enumerate(reversed(sessions), start=1):
                item["display_index"] = idx
        except Exception as e:
            return jsonify({"error": f"Failed to list sessions: {e}"}), 500
        return jsonify(sessions)

    # List sessions from the frozen base dataset (backend/databases/checkpoints.db), regardless of current user dataset
    @bp.get(f"{api_prefix}/sessions_base")
    def list_sessions_base():
        q_user = request.args.get("user_id")
        q_exp_no = request.args.get("experiment_no")
        q_exp_type = request.args.get("exp_type")  # 'self' | 'user'
        q_role = request.args.get("role")  # 'admin' to allow all sessions
        q_exp_name = request.args.get("experiment_name")
        q_variant_id = request.args.get("variant_id")
        if not q_role == 'admin' and not q_exp_type:
            q_exp_type = 'self'
        sessions = []
        import sqlite3
        import json as _json
        base_db = os.path.join(os.path.dirname(__file__), 'databases', 'checkpoints.db')
        try:
            conn = sqlite3.connect(base_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT session_id, created_at, last_updated, current_day, current_time_period, session_summary, active_npcs, game_settings FROM sessions ORDER BY created_at DESC"
            )
            for row in cur.fetchall():
                try:
                    gs = _json.loads(row["game_settings"] or '{}')
                except Exception:
                    gs = {}
                exp = gs.get('experiment') or {}
                if q_role != 'admin' and not exp:
                    continue
                if q_user and str(exp.get('user_id')) != str(q_user):
                    continue
                if q_exp_no and str(exp.get('experiment_no')) != str(q_exp_no):
                    continue
                if q_exp_type and str(exp.get('type')) != str(q_exp_type):
                    continue
                if q_exp_name and str(exp.get('experiment_name')) != str(q_exp_name):
                    continue
                if q_variant_id and str(exp.get('variant_id')) != str(q_variant_id):
                    continue
                sessions.append({
                    "session_id": row["session_id"],
                    "created_at": row["created_at"],
                    "last_updated": row["last_updated"],
                    "current_day": row["current_day"],
                    "current_time_period": row["current_time_period"],
                    "session_summary": row["session_summary"] or "",
                    "active_npcs": _json.loads(row["active_npcs"] or "[]"),
                    "experiment": exp,
                })
            for idx, item in enumerate(reversed(sessions), start=1):
                item["display_index"] = idx
            return jsonify(sessions)
        except Exception as e:
            return jsonify({"error": f"Failed to list base sessions: {e}"}), 500
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @bp.post(f"{api_prefix}/sessions")
    def create_session_alias():
        """Create a new session. Optionally accepts session_id, current_day, time_period; stores payload under game_settings.client_state."""
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        try:
            session = memory_agent.create_session(session_id)
            # Merge frontend payload under client_state for traceability
            gs = session.game_settings or {}
            gs["client_state"] = data
            session.game_settings = gs

            # Optional immediate updates
            if isinstance(data.get("current_day"), int):
                session.current_day = int(data["current_day"])  # type: ignore
            if isinstance(data.get("time_period"), str):
                try:
                    session.current_time_period = TimePeriod(data["time_period"])  # type: ignore
                except Exception:
                    pass

            memory_agent.db_manager.update_session(session)
            return jsonify({"session_id": session.session_id})
        except Exception as e:
            return jsonify({"error": f"Failed to create session: {e}"}), 500

    @bp.get(f"{api_prefix}/sessions/<session_id>")
    def get_session_alias(session_id: str):
        """Get a session by ID."""
        try:
            # Load via MemoryAgent to ensure game_settings is normalized/merged
            if not memory_agent.load_session(session_id):
                return jsonify({"error": "Session not found"}), 404
            # Merge any DB-only NPCs into character_list so frontend sees them
            try:
                _ = memory_agent.get_character_list()
            except Exception:
                pass
            session = memory_agent.current_session
            return jsonify(
                {
                    "session_id": session.session_id,
                    "created_at": session.created_at.isoformat(),
                    "last_updated": session.last_updated.isoformat(),
                    "current_day": session.current_day,
                    "current_time_period": session.current_time_period.value,
                    "session_summary": session.session_summary,
                    "active_npcs": session.active_npcs,
                    "game_settings": session.game_settings,
                    "experiment": (session.game_settings or {}).get('experiment'),
                }
            )
        except Exception as e:
            return jsonify({"error": f"Failed to get session: {e}"}), 500

    @bp.get(f"{api_prefix}/sessions/<session_id>/messages")
    def get_session_messages(session_id: str):
        """Return chronological messages across all dialogues in a session.

        Query: limit (optional, default 200)
        """
        limit = request.args.get('limit', default='200')
        try:
            lim = int(limit)
        except Exception:
            lim = 200
        try:
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.message_id, m.dialogue_id, m.sender, m.receiver, m.message_text, m.timestamp,
                           d.day, d.time_period
                    FROM messages m
                    JOIN dialogues d ON m.dialogue_id = d.dialogue_id
                    WHERE d.session_id = ?
                    ORDER BY m.timestamp ASC
                    LIMIT ?
                    """,
                    (session_id, lim),
                )
                rows = cur.fetchall()
                out = []
                for r in rows:
                    try:
                        out.append({
                            "message_id": r["message_id"],
                            "dialogue_id": r["dialogue_id"],
                            "sender": r["sender"],
                            "receiver": r["receiver"],
                            "message_text": r["message_text"],
                            "timestamp": r["timestamp"],
                            "day": r["day"],
                            "time_period": r["time_period"],
                        })
                    except Exception:
                        continue
            return jsonify({"messages": out})
        except Exception as e:
            return jsonify({"error": f"Failed to get session messages: {e}"}), 500

    @bp.get(f"{api_prefix}/sessions/<session_id>/day_periods")
    def get_session_day_periods(session_id: str):
        """Return distinct days and their available time periods for a session.

        Primary source: days table. Fallback: DISTINCT from dialogues if days is empty.
        Response:
        {
          "days": [ {"day": 1, "periods": ["morning","afternoon",...]}, ... ],
          "all_days": [1,2,...],
          "all_periods": ["morning","noon","afternoon","evening","night"]
        }
        """
        try:
            results = {}
            all_days = []
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                # Try days table first
                cur.execute(
                    "SELECT day, time_period FROM days WHERE session_id = ? ORDER BY day, time_period",
                    (session_id,),
                )
                rows = cur.fetchall() or []
                if not rows:
                    # Fallback to dialogues
                    cur.execute(
                        "SELECT DISTINCT day, time_period FROM dialogues WHERE session_id = ? ORDER BY day, time_period",
                        (session_id,),
                    )
                    rows = cur.fetchall() or []
                for r in rows:
                    day = int(r[0]) if r[0] is not None else 1
                    period = str(r[1] or '').lower()
                    s = results.setdefault(day, set())
                    if period:
                        s.add(period)
                # Build output
                days_out = []
                for d in sorted(results.keys()):
                    all_days.append(d)
                    days_out.append({
                        'day': d,
                        'periods': sorted(results[d])
                    })
            # Full set of allowed periods (for UI completeness)
            all_periods = ['morning', 'noon', 'afternoon', 'evening', 'night']
            return jsonify({
                'days': days_out,
                'all_days': all_days,
                'all_periods': all_periods,
            })
        except Exception as e:
            return jsonify({"error": f"Failed to get day periods: {e}"}), 500

    @bp.get(f"{api_prefix}/sessions/<session_id>/npcs")
    def get_session_npcs(session_id: str):
        """Return distinct NPCs for a session, sourced from npc_memories or dialogues as fallback."""
        try:
            results = []
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                # Primary source: npc_memories
                cur.execute(
                    "SELECT npc_name, character_properties FROM npc_memories WHERE session_id = ?",
                    (session_id,),
                )
                rows = cur.fetchall() or []
                if rows:
                    import json as _json
                    for r in rows:
                        name = r[0]
                        role = None
                        story = None
                        try:
                            props = _json.loads(r[1]) if r[1] else {}
                            role = props.get('role') if isinstance(props, dict) else None
                            story = props.get('story') if isinstance(props, dict) else None
                        except Exception:
                            pass
                        results.append({
                            'name': name,
                            'role': role,
                            'story': story,
                        })
                else:
                    # Fallback: union of initiator/receiver from dialogues
                    cur.execute(
                        "SELECT DISTINCT initiator FROM dialogues WHERE session_id = ?",
                        (session_id,),
                    )
                    names_i = [r[0] for r in cur.fetchall() if r and r[0]]
                    cur.execute(
                        "SELECT DISTINCT receiver FROM dialogues WHERE session_id = ?",
                        (session_id,),
                    )
                    names_r = [r[0] for r in cur.fetchall() if r and r[0]]
                    names = sorted(set(names_i + names_r))
                    results = [{ 'name': n } for n in names]
            return jsonify({ 'npcs': results })
        except Exception as e:
            return jsonify({"error": f"Failed to get session NPCs: {e}"}), 500

    @bp.post(f"{api_prefix}/sessions/<session_id>/save")
    def save_session_alias(session_id: str):
        """Save/Update session fields. Stores arbitrary payload in game_settings.client_state.
        Returns session_id and updated_at to match frontend expectations.
        """
        payload = request.get_json(silent=True) or {}
        try:
            session = memory_agent.db_manager.get_session(session_id)
            if not session:
                return jsonify({"error": "Session not found"}), 404

            # Merge client payload under game_settings.client_state
            gs = session.game_settings or {}
            client_state = gs.get("client_state") or {}
            if isinstance(client_state, dict):
                client_state.update(payload)
            else:
                client_state = payload
            gs["client_state"] = client_state
            # Optional: set experiment metadata if provided explicitly
            if isinstance(payload.get('experiment'), dict):
                gs['experiment'] = payload.get('experiment')
            session.game_settings = gs

            # Optional direct updates
            if isinstance(payload.get("current_day"), int):
                session.current_day = int(payload["current_day"])  # type: ignore
            if isinstance(payload.get("time_period"), str):
                try:
                    session.current_time_period = TimePeriod(payload["time_period"])  # type: ignore
                except Exception:
                    pass

            memory_agent.db_manager.update_session(session)
            return jsonify({
                "session_id": session.session_id,
                "updated_at": session.last_updated.isoformat(),
            })
        except Exception as e:
            return jsonify({"error": f"Failed to save session: {e}"}), 500

    # ---------------------------------------------------------------------
    # Experiments API
    # ---------------------------------------------------------------------
    @bp.get(f"{api_prefix}/experiments")
    def list_experiments():
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), 'experimental_config.json')
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": f"Failed to load experiments: {e}"}), 500

    @bp.post(f"{api_prefix}/experiments/apply")
    def apply_experiment():
        """Apply an experiment variant at runtime by setting env and updating agent configs.

        Body: {"variant_id": "..."}
        """
        payload = request.get_json(silent=True) or {}
        variant_id = payload.get('variant_id')
        if not variant_id:
            return jsonify({"error": "variant_id is required"}), 400
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), 'experimental_config.json')
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Locate variant across experiments
            target = None
            for _, exp in (data.get('experiments') or {}).items():
                for v in exp.get('variants', []):
                    if v.get('id') == variant_id:
                        target = v
                        break
                if target:
                    break
            if not target:
                return jsonify({"error": f"Variant '{variant_id}' not found"}), 404

            conf = target.get('config') or {}

            # Map to env for runtime consumption
            os.environ['AUTO_REPUTATION_UPDATE'] = '1' if conf.get('reputation_enabled', True) else '0'

            # Build agent LLM map
            agent_map = {}
            game_agents = conf.get('game_agents') or {}
            for k, v in game_agents.items():
                agent_map[k] = {"provider": v.get('provider'), "model": v.get('model')}
            social_agents = conf.get('social_agents') or {}
            for k, v in social_agents.items():
                agent_map[k] = {"provider": v.get('provider'), "model": v.get('model')}

            os.environ['GAME_AGENT_LLM_CONFIGS'] = json.dumps(agent_map)

            # Update live social agents if provided
            try:
                # Opinion
                if 'opinion_agent' in social_agents and hasattr(social_service, '_opinion'):
                    prov = social_agents['opinion_agent'].get('provider')
                    model = social_agents['opinion_agent'].get('model')
                    if prov is not None and model is not None and hasattr(social_service._opinion, 'set_llm_provider'):
                        social_service._opinion.set_llm_provider(prov, model)
                # Social stance
                if 'stance_agent' in social_agents and hasattr(social_service, '_stance'):
                    prov = social_agents['stance_agent'].get('provider')
                    model = social_agents['stance_agent'].get('model')
                    if prov is not None and model is not None and hasattr(social_service._stance, 'set_llm_provider'):
                        social_service._stance.set_llm_provider(prov, model)
                # Knowledge
                if 'knowledge_agent' in social_agents and hasattr(social_service, '_knowledge'):
                    prov = social_agents['knowledge_agent'].get('provider')
                    model = social_agents['knowledge_agent'].get('model')
                    if prov is not None and model is not None and hasattr(social_service._knowledge, 'set_llm_provider'):
                        social_service._knowledge.set_llm_provider(prov, model)
                # Reputation
                if 'reputation_agent' in social_agents and hasattr(social_service, '_reputation'):
                    prov = social_agents['reputation_agent'].get('provider')
                    model = social_agents['reputation_agent'].get('model')
                    if prov is not None and model is not None and hasattr(social_service._reputation, 'set_llm_provider'):
                        social_service._reputation.set_llm_provider(prov, model)
            except Exception:
                # Non-fatal
                pass

            return jsonify({
                'applied': True,
                'variant': target,
                'env': {
                    'AUTO_REPUTATION_UPDATE': os.environ.get('AUTO_REPUTATION_UPDATE'),
                    'GAME_AGENT_LLM_CONFIGS': os.environ.get('GAME_AGENT_LLM_CONFIGS'),
                }
            })
        except Exception as e:
            return jsonify({"error": f"Failed to apply experiment: {e}"}), 500

    @bp.post(f"{api_prefix}/experiments/clone_session")
    def clone_session_for_user():
        """Clone an existing session as a user experiment without mutating the source.

        Body: {"source_session_id": str, "user_id": str, "experiment_no": int}
        """
        payload = request.get_json(silent=True) or {}
        src_id = payload.get('source_session_id')
        user_id = payload.get('user_id')
        exp_no = payload.get('experiment_no')
        if not src_id or not user_id or exp_no is None:
            return jsonify({"error": "source_session_id, user_id, experiment_no are required"}), 400
        try:
            src = memory_agent.db_manager.get_session(src_id)
            if not src:
                return jsonify({"error": "Source session not found"}), 404
            # Compose a user-specific clone id to avoid overwriting precious experiments
            try:
                exp_meta = (src.game_settings or {}).get('experiment') or {}
                base = f"{exp_meta.get('experiment_name') or 'exp'}_{exp_meta.get('variant_id') or 'v'}_{user_id}"
            except Exception:
                base = f"exp_user_{user_id}"
            unique_id = f"{base}_{int(datetime.utcnow().timestamp())}"
            # Ensure uniqueness and avoid conflicts
            try:
                memory_agent.db_manager.delete_session_data(unique_id)
            except Exception:
                pass
            cloned = memory_agent.create_session(session_id=unique_id)
            # Copy settings and mark experiment metadata (no schema changes)
            gs = (src.game_settings or {}).copy()
            gs['experiment'] = {
                'type': 'user',
                'user_id': user_id,
                'experiment_no': exp_no,
                'scenario_source_session_id': src_id,
                'experiment_name': exp_meta.get('experiment_name'),
                'variant_id': exp_meta.get('variant_id'),
            }
            cloned.game_settings = gs
            memory_agent.db_manager.update_session(cloned)
            # Record import for metrics under this user
            try:
                from user_stats_manager import log_import as _log_import
                _log_import(getattr(memory_agent.db_manager, 'db_path', None), unique_id, src_id, user_id)
            except Exception:
                pass
            return jsonify({
                'session_id': cloned.session_id,
                'experiment': gs['experiment'],
            })
        except Exception as e:
            return jsonify({"error": f"Failed to clone session: {e}"}), 500

    # ---------------------------------------------------------------------
    # Metrics API (read-only helpers for frontend inspection)
    # ---------------------------------------------------------------------
    @bp.post(f"{api_prefix}/questionnaire/submit")
    def questionnaire_submit():
        """Persist questionnaire responses to questionnaire_responses table (maingamedata.db).

        Body: {
          user_id?: str,
          session_id?: str,
          questionnaire_id: str,
          phase: str,
          responses: [ { questionId, questionName?, response, timestamp, userId? } ]
        }
        """
        try:
            payload = request.get_json(silent=True) or {}
            # Auto-assign user_id if missing using users table pattern userN
            user_id = str(payload.get('user_id') or '').strip()
            session_id = str(payload.get('session_id') or '')
            qid = str(payload.get('questionnaire_id') or '')
            phase = str(payload.get('phase') or '')
            responses = payload.get('responses') or []
            if not qid or not isinstance(responses, list):
                return err('questionnaire_id and responses are required', 400)

            # Extract user_id from response if present and not already set
            if not user_id and responses:
                for resp in responses:
                    if isinstance(resp, dict) and resp.get('userId'):
                        user_id = str(resp.get('userId'))
                        break

            conn = get_db()
            cur = conn.cursor()
            
            # Ensure user record exists and has main_game_data entry
            try:
                if not user_id:
                    # Find max userN
                    cur.execute("SELECT user_id FROM users WHERE user_id LIKE 'user%'")
                    nums = []
                    for r in cur.fetchall() or []:
                        try:
                            sid = r[0] or ''
                            if sid.startswith('user') and sid[4:].isdigit():
                                nums.append(int(sid[4:]))
                        except Exception:
                            pass
                    next_n = (max(nums) + 1) if nums else 1
                    user_id = f"user{next_n}"
                
                # Upsert user row
                now_iso = datetime.utcnow().isoformat()
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO users (user_id, created_at, metadata) VALUES (?, ?, ?)",
                        (user_id, now_iso, json.dumps({})),
                    )
                    
                    # Ensure main_game_data exists for this user
                    try:
                        mgd = memory_agent.db_manager.get_main_game_data(user_id)
                        if not mgd:
                            memory_agent.db_manager.create_main_game_data(user_id=user_id)
                    except Exception as e:
                        print(f"Error ensuring main_game_data: {e}")
                except Exception as e:
                    print(f"Error upserting user: {e}")
            except Exception as e:
                # If anything goes wrong, fallback to anonymous
                print(f"User handling error: {e}")
                user_id = user_id or 'user1'
            # Attempt insert; if table missing (e.g., on first run), create and retry
            try:
                cur.execute(
                    """
                    INSERT INTO questionnaire_responses
                    (user_id, session_id, questionnaire_id, phase, responses_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        session_id,
                        qid,
                        phase,
                        json.dumps(responses, default=str),
                        datetime.utcnow().isoformat(),
                    ),
                )
            except Exception as ie:
                if 'no such table: questionnaire_responses' in str(ie).lower():
                    try:
                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS questionnaire_responses (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id TEXT NOT NULL,
                                session_id TEXT,
                                questionnaire_id TEXT NOT NULL,
                                phase TEXT,
                                responses_json TEXT NOT NULL,
                                created_at TEXT NOT NULL
                            )
                            """
                        )
                        cur.execute(
                            """
                            INSERT INTO questionnaire_responses
                            (user_id, session_id, questionnaire_id, phase, responses_json, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                user_id,
                                session_id,
                                qid,
                                phase,
                                json.dumps(responses, default=str),
                                datetime.utcnow().isoformat(),
                            ),
                        )
                    except Exception as ie2:
                        return err(f'Failed to initialize questionnaire table: {ie2}', 500)
                else:
                    return err(f'Failed to store questionnaire: {ie}', 500)

            conn.commit()
            # Also append responses to a CSV per questionnaire for easy export
            try:
                import csv
                metrics_dir = os.path.join(os.path.dirname(__file__), 'metrics')
                os.makedirs(metrics_dir, exist_ok=True)
                csv_path = os.path.join(metrics_dir, f'questionnaire_{qid}.csv')
                need_header = not os.path.exists(csv_path)
                with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    if need_header:
                        w.writerow(['created_at','user_id','session_id','questionnaire_id','phase','question_id','question_name','response','response_timestamp'])
                    now_iso = datetime.utcnow().isoformat()
                    for r in (responses or []):
                        qn = (r or {}).get('questionName') or (r or {}).get('question_name')
                        rid = (r or {}).get('questionId') or (r or {}).get('question_id')
                        resp = (r or {}).get('response')
                        if isinstance(resp, (list, tuple)):
                            try:
                                resp = ";".join(map(str, resp))
                            except Exception:
                                resp = str(resp)
                        ts = (r or {}).get('timestamp')
                        w.writerow([now_iso, user_id, session_id, qid, phase, rid, qn, resp, ts])
            except Exception:
                # Non-fatal if CSV export fails
                pass

            # Ensure main_game_data exists for this user
            try:
                # Create minimal main game data row if missing
                mgd = memory_agent.db_manager.get_main_game_data(user_id)
                if not mgd:
                    memory_agent.db_manager.create_main_game_data(user_id=user_id)
            except Exception:
                pass

            return ok({'ok': True, 'user_id': user_id})
        except Exception as e:
            return err(f'Failed to store questionnaire: {e}', 500)
    @bp.get(f"{api_prefix}/metrics")
    def list_metrics():
        """List available metrics files (CSV/JSON) in backend/metrics directory."""
        try:
            metrics_dir = os.path.join(os.path.dirname(__file__), 'metrics')
            if not os.path.isdir(metrics_dir):
                return jsonify([])
            files = []
            for fn in os.listdir(metrics_dir):
                if not (fn.endswith('_metrics.csv') or fn.endswith('_metrics.json')):
                    continue
                full = os.path.join(metrics_dir, fn)
                try:
                    stat = os.stat(full)
                    parts = fn.rsplit('_metrics.', 1)[0]
                    # Expect format: <experiment_id>_<session_id>
                    if '_' in parts:
                        exp_id, sess_id = parts.split('_', 1)
                    else:
                        exp_id, sess_id = parts, ''
                    files.append({
                        'file': fn,
                        'experiment_id': exp_id,
                        'session_id': sess_id,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'type': 'csv' if fn.endswith('.csv') else 'json'
                    })
                except Exception:
                    continue
            # Sort newest first
            files.sort(key=lambda x: x['modified'], reverse=True)
            return jsonify(files)
        except Exception as e:
            return jsonify({"error": f"Failed to list metrics: {e}"}), 500

    @bp.get(f"{api_prefix}/metrics/summary")
    def metrics_summary():
        exp_id = request.args.get('experiment_id') or ''
        sess_id = request.args.get('session_id') or ''
        if not exp_id or not sess_id:
            return jsonify({"error": "experiment_id and session_id are required"}), 400
        try:
            metrics_dir = os.path.join(os.path.dirname(__file__), 'metrics')
            json_path = os.path.join(metrics_dir, f"{exp_id}_{sess_id}_metrics.json")
            if not os.path.isfile(json_path):
                return jsonify({"error": "metrics json not found"}), 404
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Return summary and last few metrics entries
            metrics = data.get('metrics') or []
            tail = metrics[-10:] if isinstance(metrics, list) else []
            return jsonify({
                'summary': data.get('summary'),
                'last_metrics': tail,
                'session_id': data.get('session_id'),
                'experiment_id': data.get('experiment_id')
            })
        except Exception as e:
            return jsonify({"error": f"Failed to read metrics: {e}"}), 500

    # ---------------------------------------------------------------------
    # Social Agents API
    # ---------------------------------------------------------------------
    @bp.post(f"{api_prefix}/social/opinion")
    def api_social_opinion():
        data = request.get_json(silent=True) or {}
        required = ["name", "personality", "story", "recipient", "incoming_message"]
        missing = [k for k in required if k not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        result = social_service.generate_opinion(
            name=data["name"],
            personality=data["personality"],
            story=data["story"],
            recipient=data["recipient"],
            incoming_message=data.get("incoming_message", ""),
            dialogue=data.get("dialogue", ""),
            recipient_reputation=data.get("recipient_reputation"),
        )
        return jsonify({"opinion": result})

    @bp.post(f"{api_prefix}/social/stance")
    def api_social_stance():
        data = request.get_json(silent=True) or {}
        required = [
            "npc_name",
            "npc_personality",
            "opponent_name",
            "opponent_reputation",
            "opponent_opinion",
            "knowledge_base",
            "dialogue_memory",
            "interaction_history",
        ]
        missing = [k for k in required if k not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        result = social_service.set_social_stance(
            npc_name=data["npc_name"],
            npc_personality=data["npc_personality"],
            opponent_name=data["opponent_name"],
            opponent_reputation=data["opponent_reputation"],
            opponent_opinion=data["opponent_opinion"],
            knowledge_base=data["knowledge_base"],
            dialogue_memory=data["dialogue_memory"],
            interaction_history=data["interaction_history"],
        )
        return jsonify({"stance": result})

    @bp.post(f"{api_prefix}/social/knowledge")
    def api_social_knowledge():
        data = request.get_json(silent=True) or {}
        required = ["name", "personality", "knowledge", "dialogue"]
        missing = [k for k in required if k not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        result = social_service.analyze_knowledge(
            name=data["name"],
            personality=data["personality"],
            knowledge=data["knowledge"],
            dialogue=data["dialogue"],
        )
        return jsonify({"knowledge": result})

    @bp.post(f"{api_prefix}/social/reputation")
    def api_social_reputation():
        data = request.get_json(silent=True) or {}
        required = [
            "character_name",
            "world_definition",
            "dialogues",
        ]
        missing = [k for k in required if k not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        result = social_service.generate_reputation(
            character_name=data["character_name"],
            world_definition=data["world_definition"],
            opinions=data.get("opinions"),
            dialogues=data["dialogues"],
            current_reputation=data.get("current_reputation"),
        )
        return jsonify({"reputation": result})

    # ---------------------------------------------------------------------
    # Settings and Network (admin)
    # ---------------------------------------------------------------------
    @bp.get(f"{api_prefix}/settings")
    def get_settings():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value_json, updated_at FROM settings WHERE name='current'")
        row = cur.fetchone()
        if not row:
            return err("Settings not found", 404)
        return ok({"settings": json.loads(row["value_json"]), "updated_at": row["updated_at"]})

    @bp.get(f"{api_prefix}/settings/default")
    def get_default_settings():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM settings WHERE name='default'")
        row = cur.fetchone()
        if not row:
            return err("Default settings not found", 404)
        return ok(json.loads(row["value_json"]))

    @bp.post(f"{api_prefix}/settings/load-default")
    def load_default_settings_route():
        if not os.path.exists(default_settings_path):
            return None
        with open(default_settings_path, "r") as f:
            settings = json.load(f)
        npcs_path = os.path.join(os.path.dirname(__file__), "npcs.json")
        if os.path.exists(npcs_path):
            with open(npcs_path, "r") as f:
                npcs_data = json.load(f)
                if "npcs" in npcs_data:
                    settings["npc_templates"] = npcs_data["npcs"]
        return settings

    @bp.post(f"{api_prefix}/settings")
    def set_settings():
        payload = request.get_json(silent=True) or {}
        settings = payload.get("settings")
        if not isinstance(settings, dict):
            return err("settings must be an object", 400)
        conn = get_db()
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE settings SET value_json=?, updated_at=? WHERE name='current'",
            (json.dumps(settings), now),
        )
        conn.commit()
        return ok({"updated_at": now})

    @bp.post(f"{api_prefix}/settings/reset")
    def reset_settings():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM settings WHERE name='default'")
        row = cur.fetchone()
        if not row:
            return err("Default settings not found", 404)
        now = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE settings SET value_json=?, updated_at=? WHERE name='current'",
            (row["value_json"], now),
        )
        conn.commit()
        return ok({"reset": True, "updated_at": now})

    @bp.get(f"{api_prefix}/network")
    def get_network():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM settings WHERE name='current'")
        row = cur.fetchone()
        if not row:
            return err("Settings not found", 404)
        settings = json.loads(row["value_json"])
        return ok(settings.get("world", {}).get("ai_network", {}))

    @bp.post(f"{api_prefix}/network")
    def set_network():
        payload = request.get_json(silent=True) or {}
        network = payload.get("network")
        if not isinstance(network, dict):
            return err("network must be an object", 400)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM settings WHERE name='current'")
        row = cur.fetchone()
        if not row:
            return err("Settings not found", 404)
        settings = json.loads(row["value_json"])
        settings.setdefault("world", {})["ai_network"] = network
        now = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE settings SET value_json=?, updated_at=? WHERE name='current'",
            (json.dumps(settings), now),
        )
        conn.commit()
        return ok({"updated_at": now})

    # ---------------------------------------------------------------------
    # Experimental Configuration API
    # ---------------------------------------------------------------------
    @bp.get(f"{api_prefix}/experiments")
    def get_experiments():
        """Get available experimental configurations"""
        try:
            exp_config_path = os.path.join(os.path.dirname(__file__), "experimental_config.json")
            if not os.path.exists(exp_config_path):
                return ok({"experiments": {}, "message": "No experimental config found"})
            
            with open(exp_config_path, 'r') as f:
                config = json.load(f)
            
            return ok(config)
        except Exception as e:
            return err(f"Failed to load experimental config: {e}", 500)

    @bp.post(f"{api_prefix}/experiments/run")
    def run_experiment():
        """Start an experimental run (runner-based)"""
        payload = request.get_json(silent=True) or {}
        experiment_name = payload.get("experiment_name")
        
        if not experiment_name:
            return err("experiment_name is required", 400)
        
        try:
            from runner import run_experiment_from_app
            import threading
            def run_exp():
                try:
                    results = run_experiment_from_app(experiment_name)
                    logger.info(f"Experiment {experiment_name} completed: {results.get('success')}")
                except Exception as e:
                    logger.exception(f"Experiment {experiment_name} failed: {e}")
            
            thread = threading.Thread(target=run_exp, daemon=True)
            thread.start()
            
            return ok({
                "started": True,
                "experiment_name": experiment_name,
                "message": "Experiment started in background"
            })
            
        except Exception as e:
            return err(f"Failed to start experiment: {e}", 500)

    @bp.get(f"{api_prefix}/experiments/results")
    def get_experiment_results():
        """Get experimental results"""
        try:
            results_dir = os.path.join(os.path.dirname(__file__), "metrics")
            if not os.path.exists(results_dir):
                return ok({"results": [], "message": "No results found"})
            
            results = []
            for filename in os.listdir(results_dir):
                if filename.startswith("experiment_results_") and filename.endswith(".json"):
                    filepath = os.path.join(results_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            result = json.load(f)
                            results.append({
                                "filename": filename,
                                "experiment_name": result.get("experiment_name"),
                                "start_time": result.get("start_time"),
                                "end_time": result.get("end_time"),
                                "success": result.get("success"),
                                "variants_count": len(result.get("variants", {}))
                            })
                    except Exception as e:
                        logger.warning(f"Failed to read result file {filename}: {e}")
            
            return ok({"results": results})
            
        except Exception as e:
            return err(f"Failed to get experiment results: {e}", 500)

    @bp.get(f"{api_prefix}/experiments/sessions")
    def list_experiment_sessions_grouped():
        """List experimental sessions grouped by experiment_name and variant_id.

        Query params:
          - role=admin to include non-experimental sessions (default hides non-experimental)
          - user_id=<id> to include only user-cloned sessions for that user
          - exp_type=self|user to filter by experiment type (default self for non-admin)
        """
        q_role = request.args.get('role')
        q_user = request.args.get('user_id')
        q_exp_type = request.args.get('exp_type')
        if q_role != 'admin' and not q_exp_type:
            q_exp_type = 'self'

        grouped = {}
        try:
            with memory_agent.db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT session_id, created_at, last_updated, current_day, current_time_period, session_summary, game_settings FROM sessions ORDER BY created_at DESC"
                )
                for row in cur.fetchall():
                    try:
                        gs = json.loads(row['game_settings'] or '{}')
                    except Exception:
                        gs = {}
                    exp = gs.get('experiment') or {}

                    # Only experimental sessions unless admin override
                    if q_role != 'admin' and not exp:
                        continue
                    if q_exp_type and str(exp.get('type')) != str(q_exp_type):
                        continue
                    if q_user and str(exp.get('user_id')) != str(q_user):
                        continue

                    exp_name = str(exp.get('experiment_name') or 'unknown')
                    variant_id = str(exp.get('variant_id') or 'unknown')

                    entry = {
                        'session_id': row['session_id'],
                        'created_at': row['created_at'],
                        'last_updated': row['last_updated'],
                        'current_day': row['current_day'],
                        'current_time_period': row['current_time_period'],
                        'type': exp.get('type'),
                        'user_id': exp.get('user_id'),
                        'experiment_no': exp.get('experiment_no'),
                        'scenario_source_session_id': exp.get('scenario_source_session_id'),
                    }
                    grouped.setdefault(exp_name, {}).setdefault(variant_id, []).append(entry)

            return ok({'experiments': grouped})
        except Exception as e:
            return err(f"Failed to group experiment sessions: {e}", 500)

    return bp
