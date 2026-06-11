"""
ThinkMCP — FastMCP server exposing 13 tools across 4 categories.

Transports:
  stdio (default) — for Claude Desktop, local use, subprocess
  HTTP            — for remote / Streamlit deployment (use --http flag)
"""

import os
import sys

# Allow running as: python server/mcp_server.py [--http] [--port PORT]
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp.server.fastmcp import FastMCP

from server.tools.actions import compare, create_summary, write_report
from server.tools.memory import list_memory, recall, remember
from server.tools.reasoning import critique, plan, think
from server.tools.research import fetch_url, search_code, search_papers, web_search

mcp = FastMCP(
    name="ThinkMCP",
    instructions=(
        "You are a thinking-augmented research agent. "
        "Use the think tool liberally to reason between steps. "
        "Use critique before delivering final answers. "
        "Use remember/recall to persist findings across tool calls."
    ),
)

# ── RESEARCH TOOLS ────────────────────────────────────────────────────────────

@mcp.tool()
def web_search_tool(query: str) -> dict:
    """
    Search the web using Tavily API and return the top 5 results.
    Requires TAVILY_API_KEY environment variable.
    Returns: {query, answer, results: [{title, url, snippet, score}]}
    """
    return web_search(query)


@mcp.tool()
def fetch_url_tool(url: str) -> dict:
    """
    Fetch a URL and return its content as clean markdown-like text.
    Strips HTML tags, scripts, and styles. Truncates at 8000 chars.
    Returns: {url, content, length}
    """
    return fetch_url(url)


@mcp.tool()
def search_papers_tool(topic: str) -> dict:
    """
    Search ArXiv for academic papers on a topic and return up to 3 results.
    Uses the public ArXiv API — no API key needed.
    Returns: {topic, papers: [{title, summary, url, authors, published}], count}
    """
    return search_papers(topic)


@mcp.tool()
def search_code_tool(query: str) -> dict:
    """
    Search GitHub for code matching a query.
    Requires GITHUB_TOKEN (GitHub's code-search API needs auth; zero scopes suffice).
    Returns: {query, total_count, results: [{name, path, repo, url, score}]}
    """
    return search_code(query)


# ── REASONING TOOLS ───────────────────────────────────────────────────────────
# THINKMCP_DISABLE_REASONING=1 hides these three tools entirely — used by the
# benchmark's ablated arm so the model cannot see (not just cannot call) them.

if os.environ.get("THINKMCP_DISABLE_REASONING", "") != "1":

    @mcp.tool()
    def think_tool(thought: str) -> str:
        """
        A scratchpad for mid-workflow reasoning. Use this between tool calls to:
        - Plan next steps
        - Evaluate quality of retrieved results
        - Detect contradictions between sources
        - Decide if more information is needed
        Does NOT call any external service. Returns the thought for traceability.
        """
        return think(thought)

    @mcp.tool()
    def critique_tool(answer: str, question: str) -> dict:
        """
        Self-evaluate a draft answer before returning it to the user.
        Returns a structured quality assessment with confidence score,
        missing aspects, and a recommendation to accept or revise.
        Returns: {answer_preview, word_count, completeness, confidence,
                  missing_aspects, recommendation}
        """
        return critique(answer, question)

    @mcp.tool()
    def plan_tool(goal: str) -> dict:
        """
        Break a goal into an ordered list of actionable sub-steps.
        Detects goal type (research, comparison, implementation, summarization)
        and returns a tailored strategy.
        Returns: {goal, strategy, steps: [...], total_steps}
        """
        return plan(goal)


# ── MEMORY TOOLS ──────────────────────────────────────────────────────────────

@mcp.tool()
def remember_tool(key: str, value: str) -> dict:
    """
    Persist a key-value pair in durable memory (SQLite) for later recall.
    Use descriptive keys like 'ddim_key_claim' or 'source_A_summary'.
    Returns: {status, key, value_preview, total_keys}
    """
    return remember(key, value)


@mcp.tool()
def recall_tool(key: str) -> dict:
    """
    Retrieve a previously stored value by key.
    Returns: {status, key, value} or {status: 'not_found', available_keys}
    """
    return recall(key)


@mcp.tool()
def list_memory_tool() -> dict:
    """
    Show all key-value pairs currently stored in memory.
    Returns: {total, entries: {key: value_preview}}
    """
    return list_memory()


# ── ACTION TOOLS ──────────────────────────────────────────────────────────────

@mcp.tool()
def write_report_tool(title: str, content: str) -> dict:
    """
    Format content as a timestamped markdown report and save to ./reports/.
    The THINKMCP_REPORTS_DIR env var overrides the output directory.
    Returns: {status, filename, filepath, size_bytes, title}
    """
    return write_report(title, content)


@mcp.tool()
def create_summary_tool(text: str, max_words: int = 150) -> dict:
    """
    Condense long text to approximately max_words words using extractive summarization.
    Returns: {summary, original_words, summary_words, reduction_pct}
    """
    return create_summary(text, max_words)


@mcp.tool()
def compare_tool(item_a: str, item_b: str) -> dict:
    """
    Produce a structured comparison table skeleton for two items.
    Returns a markdown table template and list of comparison dimensions.
    Fill the table using recalled facts, then write to a report.
    Returns: {item_a, item_b, dimensions, comparison_table, note}
    """
    return compare(item_a, item_b)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ThinkMCP server")
    parser.add_argument("--http", action="store_true", help="Use Streamable HTTP transport instead of stdio")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host (default 0.0.0.0)")
    args = parser.parse_args()

    if args.http:
        print(f"[ThinkMCP] Starting HTTP server on {args.host}:{args.port}", file=sys.stderr)
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        print("[ThinkMCP] Starting stdio server", file=sys.stderr)
        mcp.run(transport="stdio")
