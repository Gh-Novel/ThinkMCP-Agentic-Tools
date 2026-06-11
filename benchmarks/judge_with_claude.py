"""
Re-judge benchmark answer pairs with Claude Sonnet via the Claude Code CLI.

The generation arms stay local (Qwen 3 via Ollama) — this script only swaps
the judge. Using a strong independent model removes the self-judging bias of
the default harness (where the same local model generates and judges).

Each pair is judged blind in BOTH orderings; an arm wins only if Sonnet picks
it both times. Inconsistent or explicit-tie verdicts count as ties.

Usage (after run_benchmark.py has written results.json):
    python benchmarks/judge_with_claude.py [--results PATH] [--model sonnet]

Requires the `claude` CLI (Claude Code) on PATH and an active subscription.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

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


def ask_claude(prompt: str, model: str) -> tuple[int, str]:
    """Run one judgment through the Claude Code CLI. Returns (winner, reason)."""
    out = subprocess.run(
        ["claude", "-p", prompt, "--model", model],
        capture_output=True, text=True, timeout=120,
    )
    raw = out.stdout.strip()
    w = re.search(r'"winner"\s*:\s*(\d)', raw)
    r = re.search(r'"reason"\s*:\s*"([^"]*)"', raw)
    return (int(w.group(1)) if w else 0), (r.group(1) if r else raw[:120])


def judge_pair(question: str, ans_reasoning: str, ans_ablated: str, model: str) -> dict:
    """Both-orders blind judgment. Consistent winner or tie."""
    # Order 1: reasoning first
    w1, r1 = ask_claude(
        JUDGE_PROMPT.format(question=question, answer_1=ans_reasoning, answer_2=ans_ablated),
        model,
    )
    # Order 2: ablated first
    w2, r2 = ask_claude(
        JUDGE_PROMPT.format(question=question, answer_1=ans_ablated, answer_2=ans_reasoning),
        model,
    )
    pick1 = {1: "reasoning", 2: "ablated", 0: "tie"}[w1]
    pick2 = {1: "ablated", 2: "reasoning", 0: "tie"}[w2]
    verdict = pick1 if pick1 == pick2 else "tie"
    return {"verdict": verdict, "order1": pick1, "order2": pick2,
            "reasons": [r1, r2]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-judge benchmark pairs with Claude Sonnet")
    parser.add_argument("--results", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results.json"))
    parser.add_argument("--model", default="sonnet")
    args = parser.parse_args()

    with open(args.results, encoding="utf-8") as f:
        data = json.load(f)

    wins = {"reasoning": 0, "ablated": 0, "tie": 0}
    for i, row in enumerate(data["results"], 1):
        if row["reasoning"].get("error") or row["ablated"].get("error"):
            row["claude_judge"] = {"verdict": "skipped (error)"}
            continue
        print(f"[{i}/{len(data['results'])}] judging: {row['question'][:60]}...", flush=True)
        result = judge_pair(
            row["question"], row["reasoning"]["answer"], row["ablated"]["answer"], args.model,
        )
        row["claude_judge"] = result
        wins[result["verdict"]] += 1
        print(f"    {result['verdict']}  (order1={result['order1']}, order2={result['order2']})",
              flush=True)

    data["summary"]["claude_judge"] = {
        "model": args.model,
        "method": "blind, both orderings; win requires consistency",
        "wins": wins,
    }
    with open(args.results, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    judged = sum(wins.values())
    print(f"\n## Claude {args.model} verdicts ({judged} questions)\n")
    print("| Arm | Wins |")
    print("|---|---|")
    print(f"| With reasoning tools | **{wins['reasoning']}/{judged}** |")
    print(f"| Without (ablated) | **{wins['ablated']}/{judged}** |")
    print(f"| Tie / inconsistent | {wins['tie']}/{judged} |")


if __name__ == "__main__":
    main()
