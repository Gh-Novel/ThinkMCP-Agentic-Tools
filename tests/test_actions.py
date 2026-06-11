"""Tests for the action tools (write_report, create_summary, compare)."""

import os

import pytest

from server.tools.actions import compare, create_summary, write_report


@pytest.fixture(autouse=True)
def tmp_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("THINKMCP_REPORTS_DIR", str(tmp_path / "reports"))


def test_write_report_saves_markdown_file():
    result = write_report("My Topic: A Review!", "Some **markdown** content.")
    assert result["status"] == "saved"
    assert os.path.exists(result["filepath"])
    with open(result["filepath"], encoding="utf-8") as f:
        body = f.read()
    assert body.startswith("# My Topic: A Review!")
    assert "Some **markdown** content." in body


def test_write_report_sanitizes_filename():
    result = write_report("a/b\\c: d?*", "content")
    assert "/" not in result["filename"]
    assert "?" not in result["filename"]
    assert result["filename"].endswith(".md")


def test_create_summary_short_text_passthrough():
    result = create_summary("Just a few words here.", max_words=150)
    assert result["summary"] == "Just a few words here."
    assert result["reduction_pct"] == 0


def test_create_summary_reduces_long_text():
    text = " ".join(
        f"Sentence number {i} contains some informative words about the topic at hand."
        for i in range(60)
    )
    result = create_summary(text, max_words=50)
    assert result["summary_words"] <= 60  # roughly within budget
    assert result["summary_words"] < result["original_words"]
    assert result["reduction_pct"] > 50


def test_create_summary_empty_text():
    result = create_summary("   ")
    assert result["summary"] == ""
    assert result["original_words"] == 0


def test_compare_builds_table_skeleton():
    result = compare("PostgreSQL", "MySQL")
    assert result["item_a"] == "PostgreSQL"
    assert "| Dimension | PostgreSQL | MySQL |" in result["comparison_table"]
    assert len(result["dimensions"]) >= 5
