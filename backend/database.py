"""
SaulGPT — Database Layer
========================
SQLite-backed persistence for users, conversations, and messages.
Replaces in-memory CONVERSATION_MEMORY for authenticated users.
"""

import json
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saulgpt.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT UNIQUE NOT NULL,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       TEXT NOT NULL DEFAULT 'New Chat',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content         TEXT NOT NULL,
            meta            TEXT,
            turn            INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_conv
            ON messages(conversation_id, turn);
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# USER OPERATIONS
# ─────────────────────────────────────────────────────────────

def create_user(email: str, username: str, password_hash: str) -> Optional[int]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
            (email, username, password_hash)
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────
# CONVERSATION OPERATIONS
# ─────────────────────────────────────────────────────────────

def create_conversation(user_id: int, title: str = "New Chat") -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (user_id, title)
    )
    conn.commit()
    conv_id = cur.lastrowid
    conn.close()
    return conv_id


def get_conversations(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "WHERE user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset)
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM conversations WHERE user_id = ?",
        (user_id,)
    ).fetchone()["cnt"]
    conn.close()
    return {"conversations": [dict(r) for r in rows], "total": total}


def get_conversation(conv_id: int, user_id: int) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "WHERE id = ? AND user_id = ?",
        (conv_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_conversation_title(conv_id: int, title: str):
    conn = _get_conn()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
        (title, conv_id)
    )
    conn.commit()
    conn.close()


def touch_conversation(conv_id: int):
    conn = _get_conn()
    conn.execute(
        "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
        (conv_id,)
    )
    conn.commit()
    conn.close()


def delete_conversation(conv_id: int, user_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id)
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ─────────────────────────────────────────────────────────────
# MESSAGE OPERATIONS
# ─────────────────────────────────────────────────────────────

def add_message(conv_id: int, role: str, content: str, meta: str = None, turn: int = 0) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, meta, turn) VALUES (?, ?, ?, ?, ?)",
        (conv_id, role, content, meta, turn)
    )
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()
    return msg_id


def get_messages(conv_id: int) -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, meta, turn, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY turn ASC",
        (conv_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_turn(conv_id: int) -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(MAX(turn), 0) as last_turn FROM messages WHERE conversation_id = ?",
        (conv_id,)
    ).fetchone()
    conn.close()
    return row["last_turn"] if row else 0


def bulk_import_messages(conv_id: int, turns: list) -> bool:
    """Import an array of turn dicts into a conversation in one transaction.
    Each turn: {"role": str, "content": str, "meta": str or dict or None}
    """
    conn = _get_conn()
    try:
        rows = []
        for i, t in enumerate(turns):
            meta = t.get("meta")
            if meta is not None and not isinstance(meta, str):
                meta = json.dumps(meta)
            rows.append((conv_id, t["role"], t["content"], meta, i + 1))
        conn.executemany(
            "INSERT INTO messages (conversation_id, role, content, meta, turn) VALUES (?, ?, ?, ?, ?)",
            rows
        )
        conn.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conv_id,)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
