"""Integration tests: the FastMCP server registers all 13 tools."""

import asyncio

from server.mcp_server import mcp

EXPECTED_TOOLS = {
    # research
    "web_search_tool",
    "fetch_url_tool",
    "search_papers_tool",
    "search_code_tool",
    # reasoning
    "think_tool",
    "critique_tool",
    "plan_tool",
    # memory
    "remember_tool",
    "recall_tool",
    "list_memory_tool",
    # actions
    "write_report_tool",
    "create_summary_tool",
    "compare_tool",
}


def test_all_13_tools_registered():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS


def test_every_tool_has_description_and_schema():
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        assert tool.description, f"{tool.name} is missing a description"
        assert tool.inputSchema.get("type") == "object", f"{tool.name} has no input schema"
