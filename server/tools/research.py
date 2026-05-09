"""Research tools: web_search, fetch_url, search_papers, search_code."""

import os
import re
import urllib.parse
import urllib.request
import json
import html


def web_search(query: str) -> dict:
    """Search the web using Tavily API, returning top 5 results."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return {"error": "TAVILY_API_KEY not set", "results": []}

    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "max_results": 5,
        "include_answer": True,
        "include_raw_content": False,
    }).encode()

    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:400],
                "score": r.get("score", 0),
            }
            for r in data.get("results", [])[:5]
        ]
        return {
            "query": query,
            "answer": data.get("answer", ""),
            "results": results,
        }
    except Exception as e:
        return {"error": str(e), "query": query, "results": []}


def fetch_url(url: str) -> dict:
    """Fetch a URL and return clean markdown-like text content."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ThinkMCP/1.0)",
            "Accept": "text/html,text/plain",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            content_type = resp.headers.get("Content-Type", "")

        if "text/html" in content_type:
            text = _html_to_text(raw)
        else:
            text = raw

        text = text.strip()
        if len(text) > 8000:
            text = text[:8000] + "\n\n[... content truncated ...]"

        return {"url": url, "content": text, "length": len(text)}
    except Exception as e:
        return {"url": url, "error": str(e), "content": ""}


def _html_to_text(html_str: str) -> str:
    """Very lightweight HTML → plain text conversion."""
    # Remove script/style blocks
    html_str = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_str, flags=re.S | re.I)
    # Replace block-level tags with newlines
    html_str = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", html_str, flags=re.I)
    # Strip remaining tags
    html_str = re.sub(r"<[^>]+>", "", html_str)
    # Decode HTML entities
    html_str = html.unescape(html_str)
    # Collapse whitespace
    html_str = re.sub(r"[ \t]+", " ", html_str)
    html_str = re.sub(r"\n{3,}", "\n\n", html_str)
    return html_str


def search_papers(topic: str) -> dict:
    """Search ArXiv for academic papers on a topic, returning up to 3 results."""
    query = urllib.parse.quote(topic)
    url = (
        f"http://export.arxiv.org/api/query"
        f"?search_query=all:{query}&start=0&max_results=3&sortBy=relevance"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "ThinkMCP/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        papers = []
        entries = re.findall(r"<entry>(.*?)</entry>", raw, re.S)
        for entry in entries[:3]:
            title = re.search(r"<title>(.*?)</title>", entry, re.S)
            summary = re.search(r"<summary>(.*?)</summary>", entry, re.S)
            arxiv_id = re.search(r"<id>(.*?)</id>", entry, re.S)
            authors = re.findall(r"<name>(.*?)</name>", entry)
            published = re.search(r"<published>(.*?)</published>", entry)

            papers.append({
                "title": (title.group(1).strip() if title else "").replace("\n", " "),
                "summary": (summary.group(1).strip()[:400] if summary else ""),
                "url": arxiv_id.group(1).strip() if arxiv_id else "",
                "authors": authors[:3],
                "published": (published.group(1).strip()[:10] if published else ""),
            })

        return {"topic": topic, "papers": papers, "count": len(papers)}
    except Exception as e:
        return {"topic": topic, "error": str(e), "papers": []}


def search_code(query: str) -> dict:
    """Search GitHub for code matching a query."""
    token = os.environ.get("GITHUB_TOKEN", "")
    encoded = urllib.parse.quote(query)
    url = f"https://api.github.com/search/code?q={encoded}&per_page=5"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ThinkMCP/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        items = [
            {
                "name": item.get("name", ""),
                "path": item.get("path", ""),
                "repo": item.get("repository", {}).get("full_name", ""),
                "url": item.get("html_url", ""),
                "score": item.get("score", 0),
            }
            for item in data.get("items", [])[:5]
        ]
        return {
            "query": query,
            "total_count": data.get("total_count", 0),
            "results": items,
        }
    except Exception as e:
        return {"query": query, "error": str(e), "results": []}
