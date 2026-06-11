"""
ThinkMCP — Streamlit UI (local-first: Ollama + Qwen 3).

Runs the thinking agent against your local Ollama server and streams the
thinking trace and tool calls into the UI live, as they happen.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime
from typing import Any

import streamlit as st

from agent.thinking_agent import run_thinking_agent

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ThinkMCP",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Base dark */
.stApp { background-color: #0d0d0d; }
[data-testid="stSidebar"] {
    background-color: #111111;
    border-right: 1px solid #1a1a1a;
}
[data-testid="stHeader"] {
    background-color: #0d0d0d !important;
    border-bottom: 1px solid #1a1a1a;
}
[data-testid="stToolbar"] { background-color: #0d0d0d !important; }
.block-container {
    padding-top: 48px !important;
    padding-bottom: 28px !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
}

/* Sidebar header */
.sb-header {
    display: flex; align-items: center; gap: 11px;
    padding: 4px 0 20px 0;
}
.sb-icon  { font-size: 28px; line-height: 1; }
.sb-title { font-size: 17px; font-weight: 700; color: #f0f0f0; letter-spacing: -0.2px; }
.sb-sub   { font-size: 11px; color: #555; margin-top: 1px; }

/* Section labels */
.sec-label {
    font-size: 10px; font-weight: 600; color: #555;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin: 6px 0 4px 0;
}

/* Status pills */
.pill-ok  { color: #34d399; font-size: 12px; }
.pill-bad { color: #f87171; font-size: 12px; }

/* Keyboard shortcut hint */
.kb-hint { font-size: 12.5px; color: #555; padding: 9px 0 0 4px; display: inline-block; }

/* Empty states */
.empty-state {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 10px; text-align: center;
    padding: 80px 20px 40px;
}
.empty-icon { font-size: 28px; opacity: 0.3; }
.empty-msg  { font-size: 13px; color: #3d3d3d; }
.empty-ans  { font-size: 13px; color: #3d3d3d; padding: 4px 0; }

/* Trace boxes */
.think-box {
    background: #111; border-left: 3px solid #7c3aed;
    border-radius: 0 4px 4px 0; padding: 10px 14px; margin: 4px 0;
    font-size: 0.84em; color: #c4c4c4; line-height: 1.55;
}
.result-box {
    background: #111; border-left: 3px solid #059669;
    border-radius: 0 4px 4px 0; padding: 10px 14px; margin: 4px 0;
    font-size: 0.82em; color: #c4c4c4; white-space: pre-wrap;
    word-break: break-word; font-family: monospace;
}
.trace-sub {
    font-size: 10px; font-weight: 600; color: #555;
    text-transform: uppercase; letter-spacing: 0.1em; margin: 8px 0 3px 0;
}

/* Inputs */
textarea, input[type="text"], input[type="password"] {
    background-color: #141414 !important;
    border: 1px solid #232323 !important;
    color: #e0e0e0 !important;
    border-radius: 6px !important;
}
textarea:focus, input:focus {
    border-color: #4f46e5 !important;
    box-shadow: 0 0 0 1px #4f46e5 !important;
}
textarea::placeholder, input::placeholder { color: #333 !important; }

/* Primary button */
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: #4f46e5 !important; border: none !important;
    border-radius: 6px !important; font-size: 13.5px !important;
    font-weight: 600 !important; padding: 7px 18px !important;
    color: #fff !important; transition: background 0.15s !important;
}
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover { background: #4338ca !important; }

/* Secondary/ghost button */
.stButton > button:not([kind="primary"]) {
    background: transparent !important; border: 1px solid #232323 !important;
    color: #666 !important; border-radius: 6px !important; font-size: 12px !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #444 !important; color: #bbb !important;
}

/* Expander — used for sidebar sections */
[data-testid="stExpander"] {
    background: transparent !important; border: none !important;
    border-bottom: 1px solid #1a1a1a !important; border-radius: 0 !important;
}
[data-testid="stExpander"] > details > summary {
    font-size: 10px !important; font-weight: 600 !important;
    color: #555 !important; text-transform: uppercase !important;
    letter-spacing: 0.1em !important; padding: 10px 0 !important;
    background: transparent !important;
}
[data-testid="stExpander"] > details > summary:hover { color: #888 !important; }
[data-testid="stExpander"] > details[open] > summary { color: #888 !important; }

/* Tabs */
[data-testid="stTabs"] { margin-top: 10px !important; }
[data-testid="stTabs"] > div > div > div > button {
    font-size: 13px !important; color: #555 !important;
    background: transparent !important; border: none !important;
    padding: 6px 14px 8px !important; font-weight: 500 !important;
}
[data-testid="stTabs"] > div > div > div > button[aria-selected="true"] {
    color: #4f46e5 !important;
    border-bottom: 2px solid #4f46e5 !important;
}
[data-testid="stTabs"] > div:first-child {
    border-bottom: 1px solid #1a1a1a !important;
}

/* Slider accent */
[data-testid="stSlider"] > div > div > div { background-color: #4f46e5 !important; }

/* Metrics */
[data-testid="stMetric"] {
    background: #111 !important; border-radius: 6px !important; padding: 10px 14px !important;
}
[data-testid="stMetricValue"] { font-size: 22px !important; color: #f0f0f0 !important; }
[data-testid="stMetricLabel"] {
    font-size: 10px !important; color: #555 !important;
    text-transform: uppercase !important; letter-spacing: 0.07em !important;
}

/* Download button */
[data-testid="stDownloadButton"] > button {
    background: #141414 !important; border: 1px solid #232323 !important;
    color: #666 !important; border-radius: 6px !important; font-size: 12px !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #4f46e5 !important; color: #818cf8 !important;
}

/* General text */
p, li, span { color: #c4c4c4; }
h1, h2, h3, h4 { color: #f0f0f0; }
code { background: #1a1a1a !important; color: #a78bfa !important; border-radius: 3px !important; }
hr { border-color: #1a1a1a !important; }
[data-testid="stCaptionContainer"] p { color: #555 !important; font-size: 11px !important; }
[data-testid="stToggle"] > label { color: #888 !important; font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────

st.session_state.setdefault("result", None)
st.session_state.setdefault("history", [])

# ── Ollama helpers ────────────────────────────────────────────────────────────


@st.cache_data(ttl=15, show_spinner=False)
def installed_models(host: str) -> list[str]:
    """List models available on the local Ollama server (empty if unreachable)."""
    try:
        import ollama

        resp = ollama.Client(host=host).list()
        return [m.model for m in resp.models]
    except Exception:
        return []


def pick_default_model(models: list[str]) -> int:
    preferred = os.environ.get("THINKMCP_MODEL", "")
    if preferred in models:
        return models.index(preferred)
    for i, m in enumerate(models):
        if m.lower().startswith("qwen3"):
            return i
    return 0


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="sb-header">
        <div class="sb-icon">🧠</div>
        <div>
            <div class="sb-title">ThinkMCP</div>
            <div class="sb-sub">Local Research Agent · Ollama</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("MODEL", expanded=True):
        st.markdown('<div class="sec-label">Ollama Host</div>', unsafe_allow_html=True)
        ollama_host = st.text_input(
            "oh", label_visibility="collapsed",
            value=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        )
        models = installed_models(ollama_host)
        st.markdown('<div class="sec-label">Model</div>', unsafe_allow_html=True)
        if models:
            model = st.selectbox(
                "om", models, index=pick_default_model(models),
                label_visibility="collapsed",
            )
            st.markdown('<span class="pill-ok">● Ollama connected</span>',
                        unsafe_allow_html=True)
        else:
            model = st.text_input(
                "om", label_visibility="collapsed",
                value=os.environ.get("THINKMCP_MODEL", "qwen3:8b"),
            )
            st.markdown('<span class="pill-bad">● Ollama not reachable — is it running?</span>',
                        unsafe_allow_html=True)

    with st.expander("SETTINGS", expanded=False):
        st.markdown('<div class="sec-label">System Prompt</div>', unsafe_allow_html=True)
        system_prompt = st.text_area(
            "sp", label_visibility="collapsed", height=155,
            value=(
                "You are ThinkMCP — a thinking-augmented research agent. "
                "Before each action, reason carefully about your approach. "
                "Use web_search_tool, fetch_url_tool, search_papers_tool and "
                "search_code_tool to gather evidence. Use critique_tool on your "
                "draft before answering. Use remember_tool to persist key findings. "
                "When done, present a thorough, well-sourced answer."
            ),
        )
        st.markdown('<div class="sec-label">Max Iterations</div>', unsafe_allow_html=True)
        max_iter = st.slider("mi", 5, 30, 20, label_visibility="collapsed")
        show_raw = st.toggle("Show raw trace JSON", value=False)

    with st.expander("API KEYS", expanded=False):
        st.caption("Only needed for web search / GitHub code search. "
                   "Everything else runs fully local.")
        st.markdown('<div class="sec-label">Tavily (web search)</div>', unsafe_allow_html=True)
        tavily_key = st.text_input(
            "tv", type="password", label_visibility="collapsed",
            value=os.environ.get("TAVILY_API_KEY", ""),
        )
        st.markdown('<div class="sec-label">GitHub (optional)</div>', unsafe_allow_html=True)
        github_token = st.text_input(
            "gh", type="password", label_visibility="collapsed",
            placeholder="(optional)",
            value=os.environ.get("GITHUB_TOKEN", ""),
        )

    # Propagate keys to env (inherited by the MCP server subprocess)
    if tavily_key:
        os.environ["TAVILY_API_KEY"] = tavily_key
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token

    # History
    if st.session_state.history:
        with st.expander("HISTORY", expanded=False):
            for i, item in enumerate(reversed(st.session_state.history[-5:])):
                label = item["query"][:36] + ("…" if len(item["query"]) > 36 else "")
                if st.button(label, key=f"hist_{i}", use_container_width=True):
                    st.session_state.result = item

# ── Main layout ───────────────────────────────────────────────────────────────

col_left, col_right = st.columns([3, 1], gap="large")

# ── Left column: query + trace ────────────────────────────────────────────────

with col_left:
    st.markdown('<div class="sec-label">Query</div>', unsafe_allow_html=True)
    query = st.text_area(
        "q", label_visibility="collapsed", height=100,
        placeholder="Compare DDIM vs DDPM sampling approaches in diffusion models",
    )

    btn_col, hint_col = st.columns([2, 5])
    with btn_col:
        run_btn = st.button("▶  Run with Thinking", type="primary", use_container_width=True)
    with hint_col:
        st.markdown('<div class="kb-hint">⌘ + Enter</div>', unsafe_allow_html=True)

    status_slot = st.empty()

    tab_trace, tab_json = st.tabs(["Thinking Trace", "Raw JSON"])

    with tab_trace:
        trace_container = st.container()
        trace_empty_slot = st.empty()

    with tab_json:
        raw_json_slot = st.empty()

# ── Right column: answer + metrics ───────────────────────────────────────────

with col_right:
    st.markdown('<div class="sec-label">Answer</div>', unsafe_allow_html=True)
    answer_slot = st.empty()

    st.markdown("---")
    st.markdown('<div class="sec-label">Metrics</div>', unsafe_allow_html=True)
    metrics_slot = st.empty()
    export_slot  = st.empty()

# ── Render helpers ────────────────────────────────────────────────────────────

def render_trace_entry(entry: dict, container: Any) -> None:
    step = entry.get("step", "?")
    if entry.get("thought"):
        with container:
            summary = entry.get("thought_summary") or "..."
            with st.expander(f"🧠 Step {step} — {summary}", expanded=False):
                st.markdown(
                    f"<div class='think-box'>{entry['thought']}</div>",
                    unsafe_allow_html=True,
                )
    elif entry.get("tool_name"):
        with container:
            with st.expander(f"🔧 Step {step} — {entry['tool_name']}", expanded=False):
                st.markdown("<div class='trace-sub'>Input</div>", unsafe_allow_html=True)
                try:
                    st.json(entry.get("tool_input", {}))
                except Exception:
                    st.code(str(entry.get("tool_input")))
                st.markdown("<div class='trace-sub'>Result</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='result-box'>{str(entry.get('tool_result',''))[:600]}</div>",
                    unsafe_allow_html=True,
                )


def render_answer_and_metrics(result: dict) -> None:
    """Fill the answer, metrics and export slots from a result dict."""
    trace   = result.get("trace", [])
    answer  = result.get("answer", "")
    elapsed = result.get("elapsed", 0.0)
    q       = result.get("query", "")

    if show_raw:
        raw_json_slot.json({"query": q, "answer": answer, "trace": trace})
    else:
        raw_json_slot.markdown('<div class="empty-ans">Enable "Show raw trace JSON" in settings.</div>',
                               unsafe_allow_html=True)

    answer_slot.markdown(answer or "*No text response generated.*")

    n_think = sum(1 for e in trace if e.get("thought"))
    n_tools = sum(1 for e in trace if e.get("tool_name"))
    tool_names = list(dict.fromkeys(e["tool_name"] for e in trace if e.get("tool_name")))

    with metrics_slot.container():
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Thinking", n_think)
        mc2.metric("Tools", n_tools)
        mc3.metric("Time", f"{elapsed:.1f}s")
        if tool_names:
            st.caption("· ".join(f"`{t}`" for t in tool_names))

    trace_md = "\n\n".join(
        f"**Step {e['step']}** — "
        + (f"🧠 {e.get('thought_summary','')}" if e.get("thought") else f"🔧 {e.get('tool_name','')}")
        for e in trace
    )
    full_md = f"# Query\n{q}\n\n# Answer\n{answer}\n\n# Trace\n{trace_md}"

    with export_slot.container():
        st.markdown("---")
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "📥 Export .md", data=full_md,
                file_name=f"thinkmcp_{datetime.now():%Y%m%d_%H%M%S}.md",
                mime="text/markdown", use_container_width=True,
            )
        with dl2:
            st.download_button(
                "📥 Export .json",
                data=json.dumps({"query": q, "answer": answer, "trace": trace}, indent=2),
                file_name=f"thinkmcp_{datetime.now():%Y%m%d_%H%M%S}.json",
                mime="application/json", use_container_width=True,
            )


def render_result(result: dict) -> None:
    """Full re-render (stored / history results)."""
    trace_empty_slot.empty()
    rendered: set = set()
    for entry in result.get("trace", []):
        key = (entry.get("step"), entry.get("tool_name") or "think")
        if key not in rendered:
            render_trace_entry(entry, trace_container)
            rendered.add(key)
    render_answer_and_metrics(result)

# ── Show stored result or empty states ────────────────────────────────────────

if st.session_state.result and not run_btn:
    render_result(st.session_state.result)
else:
    trace_empty_slot.markdown("""
    <div class="empty-state">
        <div class="empty-icon">🧠</div>
        <div class="empty-msg">Run a query to see the thinking trace</div>
    </div>
    """, unsafe_allow_html=True)
    raw_json_slot.markdown('<div class="empty-ans">No data yet.</div>', unsafe_allow_html=True)
    answer_slot.markdown('<div class="empty-ans">Run a query to see the answer here.</div>',
                         unsafe_allow_html=True)
    metrics_slot.markdown('<div class="empty-ans">No data yet.</div>', unsafe_allow_html=True)

# ── Run agent (live streaming) ────────────────────────────────────────────────

if run_btn and query.strip():
    if not models:
        st.error(f"Cannot reach Ollama at {ollama_host}. Start it with `ollama serve` "
                 f"and make sure a Qwen 3 model is pulled.")
        st.stop()

    # Clear previous output
    trace_empty_slot.empty()
    raw_json_slot.empty()
    answer_slot.empty()
    metrics_slot.empty()
    export_slot.empty()

    done_event = threading.Event()
    events: queue.Queue = queue.Queue()
    result_holder: dict = {"answer": "", "trace": [], "error": None}
    start_time = time.time()

    def _on_event(event_type: str, data: Any) -> None:
        events.put((event_type, data))

    def _run() -> None:
        try:
            answer, trace = run_thinking_agent(
                query=query,
                system_prompt=system_prompt,
                max_iterations=max_iter,
                on_event=_on_event,
                model=model,
                ollama_host=ollama_host,
            )
            result_holder["answer"] = answer
            result_holder["trace"]  = trace
        except Exception as exc:
            result_holder["error"] = str(exc)
        finally:
            done_event.set()

    threading.Thread(target=_run, daemon=True).start()

    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    frame = 0
    activity = "warming up"

    # Drain events from the agent thread and render them as they arrive.
    while not done_event.is_set() or not events.empty():
        while not events.empty():
            event_type, data = events.get_nowait()
            if event_type == "thinking":
                trace_empty_slot.empty()
                render_trace_entry(data, trace_container)
                activity = "thinking"
            elif event_type == "tool_call":
                activity = f"calling {data.get('name', 'tool')}"
            elif event_type == "tool_result":
                trace_empty_slot.empty()
                render_trace_entry(data, trace_container)
            elif event_type == "text":
                answer_slot.markdown(data.get("text", ""))
                activity = "writing answer"

        elapsed = time.time() - start_time
        status_slot.markdown(
            f"<div style='color:#555;font-size:13px;padding:4px 0'>"
            f"{frames[frame % len(frames)]} {activity}… {elapsed:.0f}s</div>",
            unsafe_allow_html=True,
        )
        frame += 1
        time.sleep(0.12)

    status_slot.empty()
    elapsed = time.time() - start_time

    if result_holder["error"]:
        st.error(f"Error: {result_holder['error']}")
        st.stop()

    result = {
        "query":   query,
        "answer":  result_holder["answer"],
        "trace":   result_holder["trace"],
        "elapsed": elapsed,
        "timestamp": datetime.now().isoformat(),
        "model": model,
    }
    st.session_state.result = result
    st.session_state.history.append(result)

    # Trace already rendered live — just fill in answer, metrics and export.
    render_answer_and_metrics(result)
