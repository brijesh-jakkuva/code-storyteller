"""SQLite storage for story history and analogy memory."""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".code-storyteller" / "stories.db"


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if not exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT NOT NULL,
            style TEXT NOT NULL,
            block TEXT DEFAULT '__all__',
            story TEXT NOT NULL,
            rating INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analogy_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept TEXT NOT NULL,
            analogy TEXT NOT NULL,
            times_used INTEGER DEFAULT 1,
            avg_rating REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_stories_filepath ON stories(filepath);
        CREATE INDEX IF NOT EXISTS idx_stories_style ON stories(style);
        CREATE INDEX IF NOT EXISTS idx_analogy_concept ON analogy_memory(concept);
    """)
    conn.commit()
    conn.close()


def save_story(filepath: str, style: str, block: str, story: str, rating: int = None):
    """Save a generated story."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO stories (filepath, style, block, story, rating) VALUES (?, ?, ?, ?, ?)",
        (filepath, style, block, story, rating),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 20) -> list[dict]:
    """Get recent story history."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM stories ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_rating(story_id: int, rating: int):
    """Rate a past story (1-5)."""
    conn = _get_conn()
    conn.execute("UPDATE stories SET rating = ? WHERE id = ?", (rating, story_id))
    conn.commit()
    conn.close()


def save_analogy(concept: str, analogy: str):
    """Save or update an analogy for a concept."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id, times_used FROM analogy_memory WHERE concept = ? AND analogy = ?",
        (concept, analogy),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE analogy_memory SET times_used = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (existing["times_used"] + 1, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO analogy_memory (concept, analogy) VALUES (?, ?)",
            (concept, analogy),
        )
    conn.commit()
    conn.close()


def get_analogy_memory(concept: str = None) -> list[dict]:
    """Get analogy memory, optionally filtered by concept."""
    conn = _get_conn()
    if concept:
        rows = conn.execute(
            "SELECT * FROM analogy_memory WHERE concept = ? ORDER BY times_used DESC",
            (concept,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analogy_memory ORDER BY times_used DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_preference(key: str, value: str):
    """Store a user preference."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_preference(key: str) -> str | None:
    """Get a user preference."""
    conn = _get_conn()
    row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None
