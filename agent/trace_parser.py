"""Extracts and formats thinking blocks and tool calls from Claude responses."""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ThinkingStep:
    step: int
    thought: str
    summary: str


@dataclass
class ToolCall:
    name: str
    input: dict
    result: str


@dataclass
class TraceEntry:
    step: int
    thinking: ThinkingStep | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""


def extract_thinking_steps(response_content: list[Any]) -> list[ThinkingStep]:
    """Pull thinking blocks out of an Anthropic response content list."""
    steps = []
    for i, block in enumerate(response_content):
        if hasattr(block, "type") and block.type == "thinking":
            thought = getattr(block, "thinking", "") or ""
            # Build a one-sentence summary (first sentence or first 120 chars)
            first_sentence = thought.split(".")[0].strip() if thought else ""
            summary = (first_sentence[:120] + "...") if len(first_sentence) > 120 else first_sentence
            steps.append(ThinkingStep(step=i, thought=thought, summary=summary))
    return steps


def extract_tool_uses(response_content: list[Any]) -> list[dict]:
    """Return list of {id, name, input} dicts for all tool_use blocks."""
    tools = []
    for block in response_content:
        if hasattr(block, "type") and block.type == "tool_use":
            tools.append({
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": getattr(block, "input", {}),
            })
    return tools


def extract_text(response_content: list[Any]) -> str:
    """Concatenate all text blocks."""
    parts = []
    for block in response_content:
        if hasattr(block, "type") and block.type == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(parts)


def format_trace_as_markdown(trace: list[TraceEntry]) -> str:
    """Render the thinking trace as a readable markdown string."""
    lines = ["# ThinkMCP — Thinking Trace\n"]
    for entry in trace:
        lines.append(f"## Step {entry.step}")
        if entry.thinking:
            lines.append(f"**🧠 Thinking:** {entry.thinking.summary}")
            lines.append(f"<details><summary>Full thought</summary>\n\n{entry.thinking.thought}\n\n</details>\n")
        for tc in entry.tool_calls:
            lines.append(f"**🔧 Tool: `{tc.name}`**")
            try:
                pretty_input = json.dumps(tc.input, indent=2)
            except Exception:
                pretty_input = str(tc.input)
            lines.append(f"```json\n{pretty_input}\n```")
            lines.append(f"📄 Result preview: `{tc.result[:200]}...`\n")
        if entry.text:
            lines.append(f"**💬 Response:** {entry.text[:300]}{'...' if len(entry.text) > 300 else ''}\n")
        lines.append("---")
    return "\n".join(lines)
