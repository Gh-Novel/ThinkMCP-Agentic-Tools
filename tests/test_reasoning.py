"""Tests for the reasoning tools (think, critique, plan)."""

from server.tools.reasoning import critique, plan, think


def test_think_returns_recorded_thought():
    out = think("I should search for primary sources first.")
    assert "[THOUGHT RECORDED]" in out
    assert "primary sources" in out


def test_critique_short_answer_scores_low():
    result = critique("Yes.", "Why does DDIM sample faster than DDPM?")
    assert result["completeness"] == "low"
    assert result["recommendation"] == "revise"
    assert "explanation of reasoning" in result["missing_aspects"]


def test_critique_long_relevant_answer_accepted():
    question = "How does DDIM sampling work?"
    answer = (
        "DDIM sampling works by defining a non-Markovian forward process that "
        "shares the same marginals as DDPM. Because the reverse process becomes "
        "deterministic, sampling can skip steps along a sub-sequence of the "
        "original diffusion trajectory. This is why DDIM achieves comparable "
        "quality with far fewer steps. The process starts from pure noise and "
        "iteratively denoises using the trained noise-prediction network, "
        "stepping through a chosen subset of timesteps until a clean sample emerges."
    )
    result = critique(answer, question)
    assert result["completeness"] in ("medium", "high")
    assert result["recommendation"] == "accept"
    assert result["missing_aspects"] == []


def test_critique_confidence_bounded():
    result = critique("word " * 200, "anything?")
    assert 0.0 <= result["confidence"] <= 0.97


def test_plan_detects_research_strategy():
    result = plan("Research the history of transformers in NLP")
    assert result["strategy"] == "research"
    assert result["total_steps"] == len(result["steps"]) > 0


def test_plan_detects_comparison_strategy():
    result = plan("Compare PostgreSQL versus MySQL for OLTP workloads")
    assert result["strategy"] == "comparison"


def test_plan_detects_implementation_strategy():
    result = plan("Build a rate limiter in Python")
    assert result["strategy"] == "implementation"


def test_plan_falls_back_to_general():
    result = plan("What is the meaning of life?")
    assert result["strategy"] == "general"
