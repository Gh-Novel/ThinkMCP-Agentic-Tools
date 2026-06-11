"""
ThinkMCP ablation benchmark: answer quality with vs. without the reasoning tools.

Two arms over a fixed question set, same model, same iteration budget:
  A "reasoning"  — all 13 tools, prompted to plan / think / self-critique
  B "ablated"    — think_tool, critique_tool and plan_tool hidden from the model

Each answer pair is then judged blind by the same local model: answers are
presented in random order with no hint of which arm produced them, and the
judge picks the better one (or a tie) on accuracy, completeness, sourcing
and clarity.

Usage:
    python benchmarks/run_benchmark.py [--model MODEL] [--judge-model MODEL]
                                       [--max-iterations N] [--trials N]

Writes benchmarks/results.json and prints a markdown summary table.
Requires a running Ollama server; no API keys needed (questions only use
ArXiv search, which is keyless).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import tempfile
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REASONING_TOOLS = {"think_tool", "critique_tool", "plan_tool"}

# Fixed question set — chosen to be answerable without any API key
# (ArXiv search is keyless; the rest is knowledge + synthesis).
QUESTIONS = [
    "Find a recent arXiv paper on diffusion model sampling efficiency and "
    "summarize its key contribution in 2-3 sentences, naming the paper.",
    "Compare DDIM and DDPM sampling approaches in terms of speed, "
    "determinism, and sample quality.",
    "Explain why standard transformer self-attention is O(n^2) in sequence "
    "length, and describe one technique that reduces this cost.",
    "Find an arXiv paper about retrieval-augmented generation and explain "
    "in plain language what problem it addresses and how.",
    "Compare SQLite and PostgreSQL for an embedded analytics use case and "
    "give a clear recommendation.",
    "What is a Mixture-of-Experts architecture in large language models, "
    "and what trade-offs does it introduce? Cite a paper if possible.",
]

PROMPT_REASONING = (
    "You are ThinkMCP — a thinking-augmented research agent. "
    "Start complex tasks with plan_tool. Before each action, use think_tool "
    "to reason about your approach. Use search_papers_tool and fetch_url_tool "
    "to gather evidence. Before answering, run critique_tool on your draft and "
    "revise if it recommends so. Present a thorough, well-sourced answer."
)

PROMPT_ABLATED = (
    "You are ThinkMCP — a research agent. "
    "Use search_papers_tool and fetch_url_tool to gather evidence. "
    "Present a thorough, well-sourced answer."
)

JUDGE_PROMPT = """You are an impartial judge. Two anonymous assistants answered the same question. Decide which answer is better overall, weighing factual accuracy, completeness, use of sources, and clarity. A longer answer is not automatically better.

QUESTION:
{question}

ANSWER 1:
{answer_1}

ANSWER 2:
{answer_2}

Respond with ONLY a JSON object, no other text:
{{"winner": 1 or 2 or 0, "reason": "<one sentence>"}}
Use 0 only if the answers are genuinely indistinguishable in quality."""


def run_arm(question: str, arm: str, model: str, max_iterations: int) -> dict:
    from agent.thinking_agent import run_thinking_agent

    exclude = None if arm == "reasoning" else REASONING_TOOLS
    prompt = PROMPT_REASONING if arm == "reasoning" else PROMPT_ABLATED

    start = time.time()
    try:
        answer, trace = run_thinking_agent(
            query=question,
            system_prompt=prompt,
            max_iterations=max_iterations,
            model=model,
            exclude_tools=exclude,
        )
        error = None
    except Exception as exc:
        answer, trace, error = "", [], str(exc)
    elapsed = time.time() - start

    return {
        "arm": arm,
        "answer": answer,
        "error": error,
        "elapsed_s": round(elapsed, 1),
        "tool_calls": sum(1 for e in trace if e.get("tool_name")),
        "reasoning_tool_calls": sum(
            1 for e in trace if e.get("tool_name") in REASONING_TOOLS
        ),
        "answer_words": len(answer.split()),
    }


def judge_pair(question: str, ans_a: str, ans_b: str, judge_model: str, rng: random.Random) -> str:
    """Blind pairwise judgment. Returns 'reasoning', 'ablated' or 'tie'."""
    import ollama

    flipped = rng.random() < 0.5
    first, second = (ans_b, ans_a) if flipped else (ans_a, ans_b)

    resp = ollama.chat(
        model=judge_model,
        messages=[{
            "role": "user",
            "content": JUDGE_PROMPT.format(
                question=question, answer_1=first, answer_2=second
            ),
        }],
        options={"temperature": 0},
    )
    raw = resp.message.content or ""
    match = re.search(r'"winner"\s*:\s*(\d)', raw)
    if not match:
        return "tie"
    winner = int(match.group(1))
    if winner == 0:
        return "tie"
    picked_first = winner == 1
    picked_b = picked_first == flipped  # first slot holds B when flipped
    return "ablated" if picked_b else "reasoning"


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkMCP reasoning-tools ablation benchmark")
    parser.add_argument("--model", default=os.environ.get("THINKMCP_MODEL", "qwen3:8b"))
    parser.add_argument("--judge-model", default=None,
                        help="Judge model (defaults to --model)")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--trials", type=int, default=1,
                        help="Judging passes per pair (majority vote)")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    judge_model = args.judge_model or args.model
    rng = random.Random(args.seed)

    # Isolate benchmark memory from the user's database.
    os.environ["THINKMCP_MEMORY_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="thinkmcp_bench_"), "memory.db"
    )
    os.environ.setdefault("THINKMCP_REPORTS_DIR", tempfile.mkdtemp(prefix="thinkmcp_bench_reports_"))

    results = []
    wins = {"reasoning": 0, "ablated": 0, "tie": 0}

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}] {question[:70]}...", flush=True)
        row: dict = {"question": question}
        for arm in ("reasoning", "ablated"):
            out = run_arm(question, arm, args.model, args.max_iterations)
            row[arm] = out
            status = out["error"] or f"{out['answer_words']}w, {out['tool_calls']} tools, {out['elapsed_s']}s"
            print(f"    {arm:<10} {status}", flush=True)

        if row["reasoning"]["error"] or row["ablated"]["error"]:
            row["verdict"] = "skipped (error)"
        else:
            votes = [
                judge_pair(question, row["reasoning"]["answer"],
                           row["ablated"]["answer"], judge_model, rng)
                for _ in range(args.trials)
            ]
            verdict = max(set(votes), key=votes.count)
            row["verdict"] = verdict
            wins[verdict] += 1
            print(f"    verdict    {verdict} {votes if args.trials > 1 else ''}", flush=True)
        results.append(row)

    judged = sum(wins.values())
    summary = {
        "model": args.model,
        "judge_model": judge_model,
        "max_iterations": args.max_iterations,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "questions": len(QUESTIONS),
        "judged": judged,
        "wins": wins,
        "avg_tool_calls": {
            arm: round(
                sum(r[arm]["tool_calls"] for r in results if not r[arm]["error"])
                / max(1, sum(1 for r in results if not r[arm]["error"])), 1)
            for arm in ("reasoning", "ablated")
        },
        "avg_elapsed_s": {
            arm: round(
                sum(r[arm]["elapsed_s"] for r in results if not r[arm]["error"])
                / max(1, sum(1 for r in results if not r[arm]["error"])), 1)
            for arm in ("reasoning", "ablated")
        },
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)

    print("\n## Results\n")
    print(f"Model: `{summary['model']}` · judge: `{summary['judge_model']}` "
          f"(blind, randomized order) · {judged} questions\n")
    print("| Arm | Wins | Avg tool calls | Avg time |")
    print("|---|---|---|---|")
    for arm, label in (("reasoning", "With reasoning tools"), ("ablated", "Without (ablated)")):
        print(f"| {label} | **{wins[arm]}/{judged}** "
              f"| {summary['avg_tool_calls'][arm]} | {summary['avg_elapsed_s'][arm]}s |")
    print(f"| Tie | {wins['tie']}/{judged} | — | — |")
    print(f"\nFull per-question data: {out_path}")


if __name__ == "__main__":
    main()
