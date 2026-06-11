"""
ThinkMCP Thinking Agent — local-first, powered by Ollama (Qwen 3).

The agent:
  1. connects to the ThinkMCP server as a real MCP client (stdio subprocess),
  2. discovers the 13 tools via the protocol (no hardcoded schemas),
  3. loops: Qwen 3 thinks -> calls tools -> reads results -> answers.

Thinking comes from the model's native reasoning stream when the model
supports it (e.g. qwen3:8b); for instruct-only variants we fall back to
parsing inline <think> tags, and the think_tool remains available either way.

Returns: (final_answer: str, thinking_trace: list[dict])
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Callable

from ollama import AsyncClient, ResponseError

from agent.mcp_client import MCPToolClient

DEFAULT_MODEL = os.environ.get("THINKMCP_MODEL", "qwen3:8b")
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
NUM_CTX = int(os.environ.get("THINKMCP_NUM_CTX", "16384"))

DEFAULT_SYSTEM_PROMPT = (
    "You are ThinkMCP — a thinking-augmented research agent. "
    "Before each action, reason carefully about your approach. "
    "Use web_search_tool, fetch_url_tool, search_papers_tool and search_code_tool "
    "to gather evidence. Use critique_tool on your draft before answering. "
    "Use remember_tool to persist key findings across steps. "
    "When done, present a thorough, well-sourced answer in plain text."
)

_THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.S)


def _split_think_tags(content: str) -> tuple[str, str]:
    """Separate inline <think>...</think> reasoning from visible content."""
    if not content:
        return "", ""
    thoughts = "\n".join(m.strip() for m in _THINK_TAG_RE.findall(content))
    visible = _THINK_TAG_RE.sub("", content).strip()
    return thoughts, visible


def _summarize(thought: str) -> str:
    first = thought.split(".")[0].strip()
    return (first[:120] + "...") if len(first) > 120 else first


def _thinking_entry(step: int, thought: str) -> dict:
    return {
        "step": step,
        "thought": thought,
        "thought_summary": _summarize(thought),
        "tool_name": None,
        "tool_input": None,
        "tool_result": None,
        "text": None,
    }


def _tool_entry(step: int, name: str, tool_input: dict, result: str) -> dict:
    return {
        "step": step,
        "thought": None,
        "thought_summary": None,
        "tool_name": name,
        "tool_input": tool_input,
        "tool_result": result[:500],
        "text": None,
    }


async def run_thinking_agent_async(
    query: str,
    system_prompt: str | None = None,
    max_iterations: int = 20,
    on_event: Callable[[str, Any], None] | None = None,
    model: str = DEFAULT_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
) -> tuple[str, list[dict]]:
    """
    Run the ThinkMCP agent on a query.

    Args:
        query: The user's question or task.
        system_prompt: Optional system prompt override.
        max_iterations: Safety cap on the tool-call loop.
        on_event: Optional callback (event_type, data) for streaming UI.
                  event_type in {'thinking', 'tool_call', 'tool_result', 'text', 'done'}
        model: Ollama model name (any tool-capable Qwen 3 variant works).
        ollama_host: Base URL of the Ollama server.

    Returns:
        (final_answer, thinking_trace) where thinking_trace is a list of dicts
        with keys: step, thought, thought_summary, tool_name, tool_input,
        tool_result, text.
    """
    client = AsyncClient(host=ollama_host)
    system = system_prompt or DEFAULT_SYSTEM_PROMPT

    thinking_trace: list[dict] = []
    step = 0
    final_answer = ""
    # Try native thinking first; instruct-only models reject it and we retry without.
    use_native_thinking = True

    def _emit(event_type: str, data: Any) -> None:
        if on_event is not None:
            try:
                on_event(event_type, data)
            except Exception:
                pass

    async with MCPToolClient() as mcp:
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]

        for _ in range(max_iterations):
            try:
                response = await client.chat(
                    model=model,
                    messages=messages,
                    tools=mcp.ollama_tools,
                    think=use_native_thinking,
                    options={"num_ctx": NUM_CTX},
                )
            except ResponseError as exc:
                if use_native_thinking and "think" in str(exc).lower():
                    use_native_thinking = False
                    continue
                raise

            msg = response.message
            content = msg.content or ""
            native_thought = getattr(msg, "thinking", None) or ""
            tag_thought, visible = _split_think_tags(content)
            thought = native_thought or tag_thought

            if thought.strip():
                entry = _thinking_entry(step, thought.strip())
                thinking_trace.append(entry)
                _emit("thinking", entry)
                step += 1

            if visible.strip():
                _emit("text", {"step": step, "text": visible})

            tool_calls = list(msg.tool_calls or [])

            if not tool_calls:
                final_answer = visible.strip()
                _emit("done", {"answer": final_answer})
                return final_answer, thinking_trace

            # Echo the assistant turn back (content + tool calls) for multi-turn.
            messages.append(
                {"role": "assistant", "content": content, "tool_calls": tool_calls}
            )

            for tc in tool_calls:
                name = tc.function.name
                arguments = dict(tc.function.arguments or {})
                _emit("tool_call", {"step": step, "name": name, "input": arguments})

                result_str = await mcp.call_tool(name, arguments)

                entry = _tool_entry(step, name, arguments, result_str)
                thinking_trace.append(entry)
                _emit("tool_result", entry)
                step += 1

                messages.append(
                    {"role": "tool", "tool_name": name, "content": result_str}
                )

    final_answer = (
        final_answer
        or "Reached maximum iterations before the model produced a final answer."
    )
    _emit("done", {"answer": final_answer})
    return final_answer, thinking_trace


def run_thinking_agent(
    query: str,
    system_prompt: str | None = None,
    max_iterations: int = 20,
    on_event: Callable[[str, Any], None] | None = None,
    model: str = DEFAULT_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
) -> tuple[str, list[dict]]:
    """Synchronous wrapper around run_thinking_agent_async."""
    return asyncio.run(
        run_thinking_agent_async(
            query=query,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            on_event=on_event,
            model=model,
            ollama_host=ollama_host,
        )
    )
