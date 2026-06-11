"""
MCP client wrapper — connects the agent to the ThinkMCP server over stdio.

The agent does NOT import tool functions directly: it spawns the MCP server
as a subprocess, discovers tools via the protocol (tools/list), and invokes
them with tools/call. This is the same path Claude Desktop / Cursor use.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(_ROOT, "server", "mcp_server.py")


class MCPToolClient:
    """Async context manager holding a live MCP session to the ThinkMCP server.

    Usage:
        async with MCPToolClient() as mcp:
            tools = mcp.ollama_tools          # schemas in Ollama/OpenAI format
            out = await mcp.call_tool("web_search_tool", {"query": "..."})
    """

    def __init__(
        self,
        server_path: str = SERVER_PATH,
        env: dict[str, str] | None = None,
        exclude_tools: set[str] | None = None,
    ):
        self._server_path = server_path
        self._env = {**os.environ, **(env or {})}
        self._exclude_tools = exclude_tools or set()
        self._stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None
        self.tools: list[Any] = []
        self.ollama_tools: list[dict] = []

    async def __aenter__(self) -> "MCPToolClient":
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable,
            args=[self._server_path],
            env=self._env,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

        listing = await self.session.list_tools()
        self.tools = [t for t in listing.tools if t.name not in self._exclude_tools]
        self.ollama_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema
                    or {"type": "object", "properties": {}, "required": []},
                },
            }
            for t in self.tools
        ]
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self.session = None

    async def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """Invoke a tool over MCP and flatten the result content to a string."""
        if self.session is None:
            raise RuntimeError("MCPToolClient is not connected — use 'async with'.")
        try:
            result = await self.session.call_tool(name, arguments=arguments or {})
        except Exception as exc:
            return json.dumps({"error": str(exc), "tool": name})

        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        flat = "\n".join(parts) if parts else ""
        if getattr(result, "isError", False):
            return json.dumps({"error": flat or "tool returned an error", "tool": name})
        return flat
