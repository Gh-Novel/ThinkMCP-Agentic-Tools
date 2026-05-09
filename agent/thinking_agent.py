"""
ThinkMCP Thinking Agent.

Sends queries to Claude with adaptive thinking enabled and all 13 MCP tools
available. Captures thinking blocks, executes tool calls, and loops until
stop_reason == 'end_turn'.

Returns: (final_answer: str, thinking_trace: list[dict])
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from agent.tool_executor import execute_tool
from agent.trace_parser import (
    extract_thinking_steps,
    extract_tool_uses,
    extract_text,
)

MODEL = "claude-sonnet-4-6"

# ── Tool schemas (passed to Claude API) ───────────────────────────────────────

MCP_TOOLS: list[dict] = [
    # RESEARCH
    {
        "name": "web_search_tool",
        "description": (
            "Search the web using Tavily API and return the top 5 results. "
            "Use for current events, facts, or anything beyond training data. "
            "Returns: {query, answer, results: [{title, url, snippet, score}]}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url_tool",
        "description": (
            "Fetch a URL and return its content as clean markdown-like text. "
            "Use when you have a specific URL to read in full. "
            "Returns: {url, content, length}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "search_papers_tool",
        "description": (
            "Search ArXiv for academic papers on a topic (up to 3 results). "
            "Use for scientific or technical research questions. "
            "Returns: {topic, papers: [{title, summary, url, authors, published}], count}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The research topic to search for"},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "search_code_tool",
        "description": (
            "Search GitHub for code examples matching a query (up to 5 results). "
            "Use for implementation examples or library usage patterns. "
            "Returns: {query, total_count, results: [{name, path, repo, url}]}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Code search query (e.g. 'FastMCP tool decorator python')"},
            },
            "required": ["query"],
        },
    },
    # REASONING
    {
        "name": "think_tool",
        "description": (
            "A scratchpad for mid-workflow reasoning. Call this to: "
            "plan next steps, evaluate result quality, detect contradictions, "
            "or decide if more info is needed. No external calls. "
            "Returns the thought for traceability."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Your internal reasoning or plan"},
            },
            "required": ["thought"],
        },
    },
    {
        "name": "critique_tool",
        "description": (
            "Self-evaluate a draft answer before returning it to the user. "
            "Returns confidence score, missing aspects, and accept/revise recommendation. "
            "Use before writing the final response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "The draft answer to evaluate"},
                "question": {"type": "string", "description": "The original question being answered"},
            },
            "required": ["answer", "question"],
        },
    },
    {
        "name": "plan_tool",
        "description": (
            "Break a goal into an ordered list of actionable sub-steps. "
            "Call this at the start of complex tasks to establish a research strategy. "
            "Returns: {goal, strategy, steps: [...], total_steps}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The goal to plan steps for"},
            },
            "required": ["goal"],
        },
    },
    # MEMORY
    {
        "name": "remember_tool",
        "description": (
            "Persist a key-value pair in session memory for later recall. "
            "Use descriptive keys like 'ddim_key_claim' or 'source_A_summary'. "
            "Returns: {status, key, value_preview, total_keys}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "A descriptive key name"},
                "value": {"type": "string", "description": "The value to store"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall_tool",
        "description": (
            "Retrieve a previously stored value by key. "
            "Returns: {status, key, value} or {status: not_found, available_keys}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The key to look up"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "list_memory_tool",
        "description": (
            "Show all key-value pairs currently stored in session memory. "
            "Returns: {total, entries: {key: value_preview}}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # ACTIONS
    {
        "name": "write_report_tool",
        "description": (
            "Format content as a timestamped markdown report and save to ./reports/. "
            "Use for final deliverables. Returns: {status, filename, filepath, size_bytes}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Report title"},
                "content": {"type": "string", "description": "Full markdown content of the report"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "create_summary_tool",
        "description": (
            "Condense long text to approximately max_words words using extractive summarization. "
            "Returns: {summary, original_words, summary_words, reduction_pct}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to summarize"},
                "max_words": {"type": "integer", "description": "Target word count (default 150)", "default": 150},
            },
            "required": ["text"],
        },
    },
    {
        "name": "compare_tool",
        "description": (
            "Produce a structured markdown comparison table skeleton for two items. "
            "Use after researching both items. Fill in the table with recalled facts. "
            "Returns: {item_a, item_b, dimensions, comparison_table, note}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_a": {"type": "string", "description": "First item to compare"},
                "item_b": {"type": "string", "description": "Second item to compare"},
            },
            "required": ["item_a", "item_b"],
        },
    },
]


# ── Agent loop ─────────────────────────────────────────────────────────────────

def run_thinking_agent(
    query: str,
    system_prompt: str | None = None,
    max_iterations: int = 20,
    on_event: object = None,  # optional callback(event_type, data)
) -> tuple[str, list[dict]]:
    """
    Run the ThinkMCP thinking agent on a query.

    Args:
        query: The user's question or task.
        system_prompt: Optional system prompt override.
        max_iterations: Safety cap on the tool-call loop.
        on_event: Optional callback invoked as (event_type, data) for streaming UI.
                  event_type ∈ {'thinking', 'tool_call', 'tool_result', 'text', 'done'}

    Returns:
        (final_answer, thinking_trace)
        thinking_trace is a list of step dicts with keys:
          step, thought, thought_summary, tool_name, tool_input, tool_result, text
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    system = system_prompt or (
        "You are ThinkMCP — a thinking-augmented research agent. "
        "Before each action, use think_tool to reason about your approach. "
        "After gathering evidence, use critique_tool to verify quality. "
        "Use remember_tool to persist key findings across steps. "
        "When done, present a thorough, well-sourced answer."
    )

    messages: list[dict] = [{"role": "user", "content": query}]
    thinking_trace: list[dict] = []
    step = 0

    def _emit(event_type: str, data: object) -> None:
        if on_event is not None:
            try:
                on_event(event_type, data)
            except Exception:
                pass

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=MODEL,
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=system,
            tools=MCP_TOOLS,
            messages=messages,
        )

        # Capture thinking blocks
        for block in response.content:
            if block.type == "thinking":
                thought = getattr(block, "thinking", "") or ""
                first = thought.split(".")[0].strip()
                summary = (first[:120] + "...") if len(first) > 120 else first
                entry = {
                    "step": step,
                    "thought": thought,
                    "thought_summary": summary,
                    "tool_name": None,
                    "tool_input": None,
                    "tool_result": None,
                    "text": None,
                }
                thinking_trace.append(entry)
                _emit("thinking", entry)
                step += 1

        # Capture any text in this turn
        for block in response.content:
            if block.type == "text":
                text = getattr(block, "text", "")
                if text.strip():
                    _emit("text", {"step": step, "text": text})

        # Done?
        if response.stop_reason == "end_turn":
            final_text = extract_text(response.content)
            _emit("done", {"answer": final_text})
            return final_text, thinking_trace

        # Process tool calls
        tool_uses = extract_tool_uses(response.content)
        if not tool_uses:
            # No tools called and not end_turn — unexpected, break safely
            final_text = extract_text(response.content)
            return final_text, thinking_trace

        # Append assistant turn (must include full content for multi-turn)
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and collect results
        tool_results = []
        for tu in tool_uses:
            _emit("tool_call", {"step": step, "name": tu["name"], "input": tu["input"]})

            result_str = execute_tool(tu["name"], tu["input"])

            _emit("tool_result", {"step": step, "name": tu["name"], "result": result_str})

            entry = {
                "step": step,
                "thought": None,
                "thought_summary": None,
                "tool_name": tu["name"],
                "tool_input": tu["input"],
                "tool_result": result_str[:500],
                "text": None,
            }
            thinking_trace.append(entry)
            step += 1

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    # Iteration cap reached — return whatever we have
    final_text = "Reached maximum iterations. Partial results:\n\n" + extract_text(
        response.content if "response" in dir() else []
    )
    return final_text, thinking_trace
