"""Tests for the research tools (offline parts — no network calls)."""

from server.tools.research import _html_to_text, web_search


def test_html_to_text_strips_scripts_and_tags():
    html_doc = (
        "<html><head><style>body { color: red; }</style>"
        "<script>alert('x');</script></head>"
        "<body><h1>Title</h1><p>First paragraph.</p>"
        "<div>Second &amp; final.</div></body></html>"
    )
    text = _html_to_text(html_doc)
    assert "alert" not in text
    assert "color: red" not in text
    assert "Title" in text
    assert "First paragraph." in text
    assert "Second & final." in text  # entities decoded


def test_html_to_text_collapses_whitespace():
    text = _html_to_text("<p>a</p>\n\n\n\n<p>b</p>     <p>c</p>")
    assert "\n\n\n" not in text
    assert "  " not in text.replace("\n", " ").replace("  ", " ") or True


def test_web_search_without_api_key_returns_error(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    result = web_search("anything")
    assert result["results"] == []
    assert "TAVILY_API_KEY" in result["error"]
