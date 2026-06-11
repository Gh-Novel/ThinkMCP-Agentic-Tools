"""Tests for the SQLite-backed memory tools."""

import pytest

from server.tools.memory import clear_memory, list_memory, recall, remember


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("THINKMCP_MEMORY_DB", str(tmp_path / "memory.db"))


def test_remember_and_recall_roundtrip():
    remember("ddim_claim", "DDIM uses a deterministic reverse process")
    result = recall("ddim_claim")
    assert result["status"] == "found"
    assert result["value"] == "DDIM uses a deterministic reverse process"


def test_remember_upserts_existing_key():
    remember("k", "first")
    remember("k", "second")
    assert recall("k")["value"] == "second"
    assert list_memory()["total"] == 1


def test_recall_missing_key_lists_available():
    remember("alpha", "1")
    result = recall("does_not_exist")
    assert result["status"] == "not_found"
    assert result["value"] is None
    assert "alpha" in result["available_keys"]


def test_list_memory_previews_long_values():
    remember("long", "x" * 200)
    entries = list_memory()["entries"]
    assert entries["long"].endswith("...")
    assert len(entries["long"]) == 83  # 80 chars + "..."


def test_memory_persists_across_connections():
    # Each tool call opens a fresh connection — simulates a server restart.
    remember("persistent", "still here")
    assert recall("persistent")["status"] == "found"


def test_clear_memory():
    remember("a", "1")
    remember("b", "2")
    assert clear_memory()["cleared"] == 2
    assert list_memory()["total"] == 0
