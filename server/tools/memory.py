"""Session memory tools: remember, recall, list_memory."""

# In-process session store (reset per server process)
_store: dict[str, str] = {}


def remember(key: str, value: str) -> dict:
    """Persist a key-value pair for the duration of this session."""
    _store[key] = value
    return {
        "status": "stored",
        "key": key,
        "value_preview": value[:100] + ("..." if len(value) > 100 else ""),
        "total_keys": len(_store),
    }


def recall(key: str) -> dict:
    """Retrieve a previously stored value by key."""
    if key not in _store:
        available = list(_store.keys())
        return {
            "status": "not_found",
            "key": key,
            "value": None,
            "available_keys": available,
        }
    return {"status": "found", "key": key, "value": _store[key]}


def list_memory() -> dict:
    """List all stored key-value pairs."""
    return {
        "total": len(_store),
        "entries": {k: (v[:80] + "..." if len(v) > 80 else v) for k, v in _store.items()},
    }


def clear_memory() -> dict:
    """Clear all stored memory (utility, not exposed as MCP tool)."""
    count = len(_store)
    _store.clear()
    return {"cleared": count}
