"""Unit tests for agent helpers (no Ollama / network required)."""

from agent.thinking_agent import _split_think_tags, _summarize, _thinking_entry, _tool_entry


def test_split_think_tags_extracts_reasoning():
    content = "<think>I should search arXiv first.</think>The answer is 42."
    thought, visible = _split_think_tags(content)
    assert thought == "I should search arXiv first."
    assert visible == "The answer is 42."


def test_split_think_tags_handles_plain_content():
    thought, visible = _split_think_tags("Just an answer.")
    assert thought == ""
    assert visible == "Just an answer."


def test_split_think_tags_handles_empty():
    assert _split_think_tags("") == ("", "")


def test_split_think_tags_multiple_blocks():
    content = "<think>one</think>middle<think>two</think>end"
    thought, visible = _split_think_tags(content)
    assert "one" in thought and "two" in thought
    assert visible == "middleend"


def test_summarize_truncates_long_first_sentence():
    summary = _summarize("x" * 300 + ". rest")
    assert len(summary) <= 123
    assert summary.endswith("...")


def test_trace_entry_shapes():
    t = _thinking_entry(0, "thinking hard")
    assert t["thought"] == "thinking hard" and t["tool_name"] is None

    e = _tool_entry(1, "web_search_tool", {"query": "q"}, "r" * 1000)
    assert e["tool_name"] == "web_search_tool"
    assert len(e["tool_result"]) == 500  # truncated for the trace
