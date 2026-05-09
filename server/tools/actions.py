"""Action tools: write_report, create_summary, compare."""

import os
import re
import textwrap
from datetime import datetime


REPORTS_DIR = os.environ.get("THINKMCP_REPORTS_DIR", "./reports")


def write_report(title: str, content: str) -> dict:
    """Format content as a markdown report and save it to disk."""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Sanitize filename
    safe_title = re.sub(r"[^\w\s-]", "", title).strip()
    safe_title = re.sub(r"\s+", "_", safe_title)[:60]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{safe_title}.md"
    filepath = os.path.join(REPORTS_DIR, filename)

    report_body = f"""# {title}

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

---

{content}
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_body)

    return {
        "status": "saved",
        "filename": filename,
        "filepath": filepath,
        "size_bytes": len(report_body.encode()),
        "title": title,
    }


def create_summary(text: str, max_words: int = 150) -> dict:
    """Condense long text to approximately max_words words."""
    if not text.strip():
        return {"summary": "", "original_words": 0, "summary_words": 0, "reduction_pct": 0}

    words = text.split()
    original_count = len(words)

    if original_count <= max_words:
        return {
            "summary": text.strip(),
            "original_words": original_count,
            "summary_words": original_count,
            "reduction_pct": 0,
            "note": "text was already within limit",
        }

    # Split into sentences (rough)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())

    # Score sentences by position and length
    scored = []
    for i, sent in enumerate(sentences):
        sent_words = len(sent.split())
        if sent_words < 5:
            continue
        # Prefer early sentences (intro), penalize very long or very short
        position_score = 1.0 / (1 + i * 0.1)
        length_score = min(1.0, sent_words / 25)
        scored.append((position_score + length_score, sent, sent_words))

    # Greedy pick until budget
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = []
    budget = max_words
    for score, sent, wc in scored:
        if wc <= budget:
            selected.append((sentences.index(sent), sent))
            budget -= wc
        if budget <= 0:
            break

    # Re-order by original position
    selected.sort(key=lambda x: x[0])
    summary = " ".join(s for _, s in selected)
    summary_words = len(summary.split())

    reduction = round((1 - summary_words / original_count) * 100, 1)

    return {
        "summary": summary,
        "original_words": original_count,
        "summary_words": summary_words,
        "reduction_pct": reduction,
    }


def compare(item_a: str, item_b: str) -> dict:
    """
    Produce a structured comparison table for two items.
    Returns a markdown table and key dimensions.
    """
    # We don't call an LLM here — we structure what we know from the names
    # and let the agent fill in facts via tool calls first, then call compare.
    dimensions = [
        "Definition / Overview",
        "Key strengths",
        "Key weaknesses / limitations",
        "Best use cases",
        "Performance characteristics",
        "Adoption / ecosystem",
        "Learning curve",
        "Cost / availability",
    ]

    # Build a markdown comparison table skeleton
    table_rows = ["| Dimension | {a} | {b} |".format(a=item_a[:30], b=item_b[:30]),
                  "|---|---|---|"]
    for dim in dimensions:
        table_rows.append(f"| {dim} | *to be filled* | *to be filled* |")

    table = "\n".join(table_rows)

    return {
        "item_a": item_a,
        "item_b": item_b,
        "dimensions": dimensions,
        "comparison_table": table,
        "note": (
            "Use this as a template. Fill in the cells by recalling stored facts "
            "or performing additional research, then call write_report with the completed table."
        ),
    }
