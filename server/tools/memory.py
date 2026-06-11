"""Persistent memory tools: remember, recall, list_memory.

Backed by SQLite so memory survives server restarts (the agent spawns a fresh
MCP server subprocess per run). Override the location with THINKMCP_MEMORY_DB;
it defaults to ./thinkmcp_memory.db in the working directory.
"""

import os
import sqlite3
from datetime import datetime


def _db_path() -> str:
    return os.environ.get("THINKMCP_MEMORY_DB", "./thinkmcp_memory.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memory ("
        "key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    return conn


def _preview(value: str, limit: int) -> str:
    return value[:limit] + ("..." if len(value) > limit else "")


def remember(key: str, value: str) -> dict:
    """Persist a key-value pair (upsert)."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO memory (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, datetime.now().isoformat()),
        )
        total = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
    return {
        "status": "stored",
        "key": key,
        "value_preview": _preview(value, 100),
        "total_keys": total,
    }


def recall(key: str) -> dict:
    """Retrieve a previously stored value by key."""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
        if row is None:
            available = [r[0] for r in conn.execute("SELECT key FROM memory ORDER BY key")]
            return {
                "status": "not_found",
                "key": key,
                "value": None,
                "available_keys": available,
            }
    return {"status": "found", "key": key, "value": row[0]}


def list_memory() -> dict:
    """List all stored key-value pairs (values previewed)."""
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM memory ORDER BY key").fetchall()
    return {
        "total": len(rows),
        "entries": {k: _preview(v, 80) for k, v in rows},
    }


def clear_memory() -> dict:
    """Clear all stored memory (utility, not exposed as an MCP tool)."""
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        conn.execute("DELETE FROM memory")
    return {"cleared": count}
