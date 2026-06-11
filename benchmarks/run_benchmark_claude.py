"""
Sonnet-hosted variant of the ablation benchmark.

Same fixed questions, same two arms, same turn budget as run_benchmark.py —
but the agent is Claude Sonnet (via the Claude Code CLI) connected to the
ThinkMCP server over real MCP (--mcp-config). This measures whether the
reasoning tools help a frontier model, complementing the local Qwen 3 run.

Arm A sees all 13 tools; arm B's server starts with
THINKMCP_DISABLE_REASONING=1, hiding think/critique/plan from tools/list.
Built-in Claude Code tools (web search, bash, file edits) are disallowed so
ThinkMCP's tools are the only capability — and to match the Qwen run, no
Tavily/GitHub keys are passed in.

Usage:
    python benchmarks/run_benchmark_claude.py [--model sonnet] [--max-turns 16]

Writes benchmarks/results_claude.json (same shape as results.json), so the
verdicts come from: python benchmarks/judge_with_claude.py --results
benchmarks/results_claude.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

_BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_BENCH_DIR)
sys.path.insert(0, _BENCH_DIR)

from run_benchmark import PROMPT_ABLATED, PROMPT_REASONING, QUESTIONS  # noqa: E402

SERVER_PATH = os.path.join(_ROOT, "server", "mcp_server.py")
PYTHON = sys.executable

DISALLOWED_BUILTINS = "Bash,Edit,Write,NotebookEdit,WebSearch,WebFetch,Task,Glob,Grep,Read"


def _mcp_config(workdir: str, ablated: bool) -> str:
    """Write an MCP config pointing at the ThinkMCP server; return its path."""
    env = {
        "THINKMCP_MEMORY_DB": os.path.join(workdir, "memory.db"),
        "THINKMCP_REPORTS_DIR": os.path.join(workdir, "reports"),
        # Match the local Qwen run: no search keys.
        "TAVILY_API_KEY": "",
        "GITHUB_TOKEN": "",
    }
    if ablated:
        env["THINKMCP_DISABLE_REASONING"] = "1"
    config = {
        "mcpServers": {
            "thinkmcp": {"command": PYTHON, "args": [SERVER_PATH], "env": env}
        }
    }
    path = os.path.join(workdir, "mcp.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    return path


def run_arm(question: str, arm: str, model: str, max_turns: int) -> dict:
    workdir = tempfile.mkdtemp(prefix=f"thinkmcp_claude_{arm}_")
    config_path = _mcp_config(workdir, ablated=(arm == "ablated"))
    prompt = PROMPT_REASONING if arm == "reasoning" else PROMPT_ABLATED

    cmd = [
        "claude", "-p", question,
        "--model", model,
        "--mcp-config", config_path,
        "--strict-mcp-config",
        "--allowedTools", "mcp__thinkmcp",
        "--disallowedTools", DISALLOWED_BUILTINS,
        "--append-system-prompt", prompt,
        "--max-turns", str(max_turns),
        "--output-format", "json",
    ]

    start = time.time()
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, cwd=workdir,
        )
        payload = json.loads(out.stdout) if out.stdout.strip() else {}
        answer = payload.get("result", "") or ""
        error = None if answer else (payload.get("subtype") or out.stderr[:200] or "empty result")
        num_turns = payload.get("num_turns", 0)
    except Exception as exc:
        answer, error, num_turns = "", str(exc), 0
    elapsed = time.time() - start

    return {
        "arm": arm,
        "answer": answer,
        "error": error,
        "elapsed_s": round(elapsed, 1),
        "num_turns": num_turns,
        "answer_words": len(answer.split()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkMCP ablation benchmark — Sonnet host")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--max-turns", type=int, default=16)
    args = parser.parse_args()

    results = []
    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}] {question[:70]}...", flush=True)
        row: dict = {"question": question}
        for arm in ("reasoning", "ablated"):
            out = run_arm(question, arm, args.model, args.max_turns)
            row[arm] = out
            status = out["error"] or (
                f"{out['answer_words']}w, {out['num_turns']} turns, {out['elapsed_s']}s"
            )
            print(f"    {arm:<10} {status}", flush=True)
        results.append(row)

    summary = {
        "agent": f"claude-code/{args.model} + ThinkMCP over MCP",
        "max_turns": args.max_turns,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "questions": len(QUESTIONS),
    }
    out_path = os.path.join(_BENCH_DIR, "results_claude.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {out_path}")
    print("Judge with: python benchmarks/judge_with_claude.py --results", out_path)


if __name__ == "__main__":
    main()
