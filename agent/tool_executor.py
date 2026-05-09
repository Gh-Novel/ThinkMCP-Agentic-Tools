"""
Routes Claude tool calls to the corresponding MCP tool implementations.
Runs the tools in-process (no subprocess/network hop needed for stdio transport).
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from server.tools.research import web_search, fetch_url, search_papers, search_code
from server.tools.reasoning import think, critique, plan
from server.tools.memory import remember, recall, list_memory
from server.tools.actions import write_report, create_summary, compare


# Map MCP tool names → callables
_TOOL_MAP = {
    "web_search_tool": lambda inp: web_search(inp["query"]),
    "fetch_url_tool": lambda inp: fetch_url(inp["url"]),
    "search_papers_tool": lambda inp: search_papers(inp["topic"]),
    "search_code_tool": lambda inp: search_code(inp["query"]),
    "think_tool": lambda inp: think(inp["thought"]),
    "critique_tool": lambda inp: critique(inp["answer"], inp["question"]),
    "plan_tool": lambda inp: plan(inp["goal"]),
    "remember_tool": lambda inp: remember(inp["key"], inp["value"]),
    "recall_tool": lambda inp: recall(inp["key"]),
    "list_memory_tool": lambda inp: list_memory(),
    "write_report_tool": lambda inp: write_report(inp["title"], inp["content"]),
    "create_summary_tool": lambda inp: create_summary(inp["text"], inp.get("max_words", 150)),
    "compare_tool": lambda inp: compare(inp["item_a"], inp["item_b"]),
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a named tool and return a JSON-serialisable string result."""
    import json

    handler = _TOOL_MAP.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = handler(tool_input)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc), "tool": tool_name})
