import sqlite3
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional
import io
import csv


def _conn(db_path: Optional[str]):
    if not db_path:
        raise ValueError("db_path required for stats operations")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def estimate_tokens(text: str) -> int:
    return int(len((text or '').split()) * 1.3)


def append_event(db_path: Optional[str], event: Dict[str, Any], user_id: Optional[str] = None) -> None:
    try:
        with _conn(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_events (user_id, session_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    event.get('session_id'),
                    event.get('type') or '',
                    json.dumps(event),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
    except Exception:
        pass


def _ensure_session_metrics(conn, session_id: str, user_id: Optional[str] = None):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM session_metrics WHERE session_id=?", (session_id,))
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO session_metrics (session_id, user_id, total_time_ms, num_user_messages, num_npc_messages, num_keystrokes, approx_tokens_in, approx_tokens_out, imports_count, last_updated)
            VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, ?)
            """,
            (session_id, user_id, datetime.utcnow().isoformat()),
        )


def log_session_start(db_path: Optional[str], session_id: str, user_id: Optional[str] = None) -> None:
    try:
        with _conn(db_path) as conn:
            cur = conn.cursor()
            _ensure_session_metrics(conn, session_id, user_id)
            cur.execute(
                "UPDATE session_metrics SET last_started_at=?, last_updated=? WHERE session_id=?",
                (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), session_id),
            )
            conn.commit()
        append_event(db_path, {"type": "game_started", "session_id": session_id}, user_id)
    except Exception:
        pass


def log_session_stop(db_path: Optional[str], session_id: str, user_id: Optional[str] = None) -> None:
    try:
        with _conn(db_path) as conn:
            cur = conn.cursor()
            _ensure_session_metrics(conn, session_id, user_id)
            cur.execute("SELECT last_started_at, total_time_ms FROM session_metrics WHERE session_id=?", (session_id,))
            row = cur.fetchone()
            total = int(row[1] or 0) if row else 0
            last_start = None
            try:
                last_start = datetime.fromisoformat(row[0]) if row and row[0] else None
            except Exception:
                last_start = None
            if last_start:
                delta_ms = int((datetime.utcnow() - last_start).total_seconds() * 1000)
                total += max(delta_ms, 0)
            cur.execute(
                "UPDATE session_metrics SET total_time_ms=?, last_started_at=NULL, last_updated=? WHERE session_id=?",
                (total, datetime.utcnow().isoformat(), session_id),
            )
            conn.commit()
        append_event(db_path, {"type": "game_stopped", "session_id": session_id}, user_id)
    except Exception:
        pass


def log_import(db_path: Optional[str], target_session_id: str, source_session_id: str, user_id: Optional[str] = None) -> None:
    try:
        with _conn(db_path) as conn:
            cur = conn.cursor()
            _ensure_session_metrics(conn, target_session_id, user_id)
            cur.execute(
                "INSERT INTO session_imports (session_id, source_session_id, time) VALUES (?, ?, ?)",
                (target_session_id, source_session_id, datetime.utcnow().isoformat()),
            )
            # Update counters
            cur.execute(
                "UPDATE session_metrics SET imports_count = COALESCE(imports_count,0)+1, last_import_source=?, last_updated=? WHERE session_id=?",
                (source_session_id, datetime.utcnow().isoformat(), target_session_id),
            )
            conn.commit()
        append_event(db_path, {"type": "checkpoint_imported", "target_session_id": target_session_id, "source_session_id": source_session_id}, user_id)
    except Exception:
        pass


def log_user_message(db_path: Optional[str], session_id: str, text: str, keystrokes: Optional[int], tokens_override: Optional[int] = None, user_id: Optional[str] = None) -> None:
    try:
        toks = int(tokens_override) if tokens_override is not None else estimate_tokens(text or '')
        with _conn(db_path) as conn:
            cur = conn.cursor()
            _ensure_session_metrics(conn, session_id, user_id)
            cur.execute(
                """
                UPDATE session_metrics SET
                    num_user_messages = COALESCE(num_user_messages,0) + 1,
                    num_keystrokes = COALESCE(num_keystrokes,0) + ?,
                    approx_tokens_in = COALESCE(approx_tokens_in,0) + ?,
                    last_updated = ?
                WHERE session_id=?
                """,
                (int(keystrokes or 0), toks, datetime.utcnow().isoformat(), session_id),
            )
            conn.commit()
        append_event(db_path, {"type": "message_user", "session_id": session_id, "len": len(text or ''), "keystrokes": keystrokes, "tokens": toks}, user_id)
    except Exception:
        pass


def log_npc_message(db_path: Optional[str], session_id: str, text: str, user_id: Optional[str] = None) -> None:
    try:
        toks = estimate_tokens(text or '')
        with _conn(db_path) as conn:
            cur = conn.cursor()
            _ensure_session_metrics(conn, session_id, user_id)
            cur.execute(
                """
                UPDATE session_metrics SET
                    num_npc_messages = COALESCE(num_npc_messages,0) + 1,
                    approx_tokens_out = COALESCE(approx_tokens_out,0) + ?,
                    last_updated = ?
                WHERE session_id=?
                """,
                (toks, datetime.utcnow().isoformat(), session_id),
            )
            conn.commit()
        append_event(db_path, {"type": "message_npc", "session_id": session_id, "len": len(text or '')}, user_id)
    except Exception:
        pass


def read_stats(db_path: Optional[str], user_id: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"events": [], "sessions": {}}
    try:
        with _conn(db_path) as conn:
            cur = conn.cursor()
            # Sessions metrics
            if user_id:
                cur.execute("SELECT * FROM session_metrics WHERE user_id=? ORDER BY last_updated DESC", (user_id,))
            else:
                cur.execute("SELECT * FROM session_metrics ORDER BY last_updated DESC")
            for row in cur.fetchall():
                sid = row["session_id"]
                out["sessions"][sid] = {
                    "total_time_ms": int(row["total_time_ms"] or 0),
                    "num_user_messages": int(row["num_user_messages"] or 0),
                    "num_npc_messages": int(row["num_npc_messages"] or 0),
                    "num_keystrokes": int(row["num_keystrokes"] or 0),
                    "approx_tokens_in": int(row["approx_tokens_in"] or 0),
                    "approx_tokens_out": int(row["approx_tokens_out"] or 0),
                    "imports_count": int(row["imports_count"] or 0),
                    "last_import_source": row["last_import_source"] or '',
                }
            # Recent events (limit)
            if user_id:
                cur.execute("SELECT event_type, payload, created_at FROM user_events WHERE user_id=? ORDER BY id DESC LIMIT 200", (user_id,))
            else:
                cur.execute("SELECT event_type, payload, created_at FROM user_events ORDER BY id DESC LIMIT 200")
            for row in cur.fetchall():
                try:
                    payload = json.loads(row["payload"] or '{}')
                except Exception:
                    payload = {}
                payload["time"] = row["created_at"]
                out["events"].append(payload)
    except Exception:
        pass
    return out


def group_by_checkpoint(stats: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    """Group per-session aggregates by checkpoint (last imported source_session_id)."""
    if db_path:
        try:
            with _conn(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT session_id, source_session_id FROM session_imports ORDER BY time")
                last_map: Dict[str, str] = {}
                for r in cur.fetchall():
                    last_map[str(r[0])] = str(r[1])
        except Exception:
            last_map = {}
    else:
        last_map = {}
    grouped: Dict[str, Dict[str, Any]] = {}
    sessions = stats.get('sessions') or {}
    for sid, s in sessions.items():
        key = last_map.get(sid) or 'fresh'
        g = grouped.setdefault(key, {
            'sessions_count': 0,
            'total_time_ms': 0,
            'num_user_messages': 0,
            'num_npc_messages': 0,
            'num_keystrokes': 0,
            'approx_tokens_in': 0,
            'approx_tokens_out': 0,
        })
        g['sessions_count'] += 1
        g['total_time_ms'] += int(s.get('total_time_ms', 0))
        g['num_user_messages'] += int(s.get('num_user_messages', 0))
        g['num_npc_messages'] += int(s.get('num_npc_messages', 0))
        g['num_keystrokes'] += int(s.get('num_keystrokes', 0))
        g['approx_tokens_in'] += int(s.get('approx_tokens_in', 0))
        g['approx_tokens_out'] += int(s.get('approx_tokens_out', 0))
    return grouped


def generate_csv(stats: Dict[str, Any], view: str = 'session', db_path: Optional[str] = None) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    if view == 'checkpoint':
        grp = group_by_checkpoint(stats, db_path)
        writer.writerow(['checkpoint_id', 'sessions_count', 'total_time_s', 'user_msgs', 'npc_msgs', 'keystrokes', 'tokens_in', 'tokens_out'])
        for ck, g in grp.items():
            writer.writerow([
                ck,
                g.get('sessions_count', 0),
                round(float(g.get('total_time_ms', 0))/1000.0, 2),
                g.get('num_user_messages', 0),
                g.get('num_npc_messages', 0),
                g.get('num_keystrokes', 0),
                g.get('approx_tokens_in', 0),
                g.get('approx_tokens_out', 0),
            ])
    else:
        sessions = stats.get('sessions') or {}
        writer.writerow(['session_id', 'total_time_s', 'user_msgs', 'npc_msgs', 'keystrokes', 'tokens_in', 'tokens_out', 'imports_count', 'last_import_source'])
        for sid, s in sessions.items():
            writer.writerow([
                sid,
                round(float(s.get('total_time_ms', 0))/1000.0, 2),
                s.get('num_user_messages', 0),
                s.get('num_npc_messages', 0),
                s.get('num_keystrokes', 0),
                s.get('approx_tokens_in', 0),
                s.get('approx_tokens_out', 0),
                s.get('imports_count', 0),
                s.get('last_import_source', ''),
            ])
    return buf.getvalue()
