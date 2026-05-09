"""Reasoning tools: think, critique, plan."""

import re


def think(thought: str) -> str:
    """
    A designated scratchpad for mid-workflow reasoning.
    Returns the thought so it appears in the conversation trace.
    No external calls — the value is the reasoning space itself.
    """
    return f"[THOUGHT RECORDED]\n{thought}"


def critique(answer: str, question: str) -> dict:
    """
    Self-evaluate an answer before returning it to the user.
    Returns a structured quality assessment.
    """
    # Heuristic quality assessment (no LLM call — keeps it fast & deterministic)
    word_count = len(answer.split())
    question_words = set(re.findall(r"\w+", question.lower()))
    answer_words = set(re.findall(r"\w+", answer.lower()))

    # Rough keyword overlap score
    overlap = len(question_words & answer_words) / max(len(question_words), 1)
    coverage_score = min(1.0, overlap * 2)

    # Length heuristic
    if word_count < 20:
        completeness = "low"
        confidence = 0.4
    elif word_count < 80:
        completeness = "medium"
        confidence = 0.65
    else:
        completeness = "high"
        confidence = 0.80

    # Adjust for keyword coverage
    confidence = min(0.97, confidence + coverage_score * 0.15)

    missing = []
    if "why" in question.lower() and "because" not in answer.lower():
        missing.append("explanation of reasoning")
    if "how" in question.lower() and word_count < 50:
        missing.append("step-by-step details")
    if "compare" in question.lower() and "however" not in answer.lower():
        missing.append("explicit comparison")

    recommendation = "accept" if confidence >= 0.65 and not missing else "revise"

    return {
        "answer_preview": answer[:200] + ("..." if len(answer) > 200 else ""),
        "question": question,
        "word_count": word_count,
        "completeness": completeness,
        "confidence": round(confidence, 2),
        "missing_aspects": missing,
        "recommendation": recommendation,
    }


def plan(goal: str) -> dict:
    """
    Break a goal into actionable sub-steps.
    Returns an ordered list of steps with rationale.
    """
    # Heuristic planning based on goal type detection
    goal_lower = goal.lower()

    if any(kw in goal_lower for kw in ["research", "find", "search", "discover"]):
        steps = [
            "Define the scope and key questions to answer",
            "Search for primary sources using web_search",
            "Search for academic papers using search_papers if applicable",
            "Retrieve full content of the most relevant sources with fetch_url",
            "Store key findings in memory using remember",
            "Synthesize findings into a coherent answer",
            "Critique the answer for completeness using critique",
            "Write a final report with write_report",
        ]
        strategy = "research"
    elif any(kw in goal_lower for kw in ["compare", "versus", "vs", "difference"]):
        steps = [
            "Identify the items to compare and comparison criteria",
            "Research item A — gather facts, use web_search / search_papers",
            "Research item B — gather facts, use web_search / search_papers",
            "Store key facts for each item with remember",
            "Use compare tool to produce a structured comparison",
            "Critique the comparison for balance and accuracy",
            "Summarize key takeaways",
        ]
        strategy = "comparison"
    elif any(kw in goal_lower for kw in ["code", "implement", "build", "create"]):
        steps = [
            "Clarify requirements and constraints",
            "Search for existing solutions or libraries with search_code",
            "Plan the implementation approach",
            "Implement step by step",
            "Test and validate",
            "Write documentation with write_report",
        ]
        strategy = "implementation"
    elif any(kw in goal_lower for kw in ["summarize", "summary", "explain"]):
        steps = [
            "Identify the source material",
            "Fetch or recall the content",
            "Identify key themes and main points",
            "Create a structured summary with create_summary",
            "Critique for accuracy and completeness",
        ]
        strategy = "summarization"
    else:
        steps = [
            "Understand the goal and clarify any ambiguities",
            "Gather necessary information",
            "Break the problem into smaller sub-tasks",
            "Execute each sub-task in order",
            "Synthesize results",
            "Review and refine",
        ]
        strategy = "general"

    return {
        "goal": goal,
        "strategy": strategy,
        "steps": steps,
        "total_steps": len(steps),
    }
