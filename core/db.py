"""
VII Conversation Database — SQLite persistence.
Stores conversations across sessions so VII remembers.

Developed by The 747 Lab
"""

import sqlite3
import os
import json
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vii.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            title TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL NOT NULL,
            actions TEXT DEFAULT '[]',
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)
    conn.commit()
    return conn


def new_conversation(title=""):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO conversations (created_at, title) VALUES (?, ?)",
        (time.time(), title)
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def add_message(conversation_id, role, content, actions=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, timestamp, actions) VALUES (?, ?, ?, ?, ?)",
        (conversation_id, role, content, time.time(), json.dumps(actions or []))
    )
    conn.commit()
    conn.close()


def get_messages(conversation_id, limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT ?",
        (conversation_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def get_recent_conversations(limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, created_at, title FROM conversations ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "created_at": r[1], "title": r[2]} for r in rows]


def get_latest_conversation():
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM conversations ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None
