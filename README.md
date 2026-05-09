# ThinkMCP

A thinking-augmented MCP (Model Context Protocol) server that gives Claude deep research and reasoning tools. When connected, Claude can search the web, read URLs, find academic papers, search GitHub, plan multi-step tasks, record thoughts, manage in-session memory, and write reports — all while exposing its reasoning trace.

## What It Is

ThinkMCP wraps 13 tools across four categories into a single MCP server:

| Category  | Tools |
|-----------|-------|
| Research  | `web_search`, `fetch_url`, `search_papers`, `search_code` |
| Reasoning | `think`, `critique`, `plan` |
| Memory    | `remember`, `recall`, `list_memory` |
| Actions   | `write_report`, `create_summary`, `compare` |

It ships with two interfaces:
- **Streamlit UI** (`app.py`) — interactive research assistant with visible thinking trace, tool call log, and markdown export
- **MCP server** (`server/mcp_server.py`) — connects directly to Claude Desktop, Cursor, VS Code, or any MCP-compatible host

## Requirements

- Python 3.12+
- `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com)
- `TAVILY_API_KEY` — [tavily.com](https://tavily.com) (web search)
- `GITHUB_TOKEN` — optional, raises GitHub API rate limits for code search

## Install

```bash
git clone https://github.com/yourname/thinkmcp
cd thinkmcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set your keys:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export TAVILY_API_KEY="tvly-..."
export GITHUB_TOKEN="ghp_..."          # optional
```

## Run the Streamlit UI

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Enter a query, watch thinking steps and tool calls stream in real time, then export the session as markdown or JSON.

## Add to Claude Desktop

1. Find your config file:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the server block (replace the paths and keys):

```json
{
  "mcpServers": {
    "thinkmcp": {
      "command": "python",
      "args": ["/absolute/path/to/thinkmcp/server/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "TAVILY_API_KEY": "tvly-...",
        "GITHUB_TOKEN": "ghp_...",
        "THINKMCP_REPORTS_DIR": "/absolute/path/to/thinkmcp/reports"
      }
    }
  }
}
```

3. Restart Claude Desktop. You'll see ThinkMCP listed under connected servers.

## Add to Cursor

1. Open **Cursor Settings** → **MCP** → **Add MCP Server**
2. Paste this config:

```json
{
  "mcpServers": {
    "thinkmcp": {
      "command": "python",
      "args": ["/absolute/path/to/thinkmcp/server/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "TAVILY_API_KEY": "tvly-...",
        "GITHUB_TOKEN": "ghp_...",
        "THINKMCP_REPORTS_DIR": "/absolute/path/to/thinkmcp/reports"
      }
    }
  }
}
```

3. Save and reload the window.

## Add to VS Code (Copilot / MCP extension)

With the [MCP extension](https://marketplace.visualstudio.com/items?itemName=anthropics.claude-vscode) or a compatible client, add to your `.vscode/mcp.json`:

```json
{
  "servers": {
    "thinkmcp": {
      "type": "stdio",
      "command": "python",
      "args": ["/absolute/path/to/thinkmcp/server/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "TAVILY_API_KEY": "tvly-...",
        "GITHUB_TOKEN": "ghp_...",
        "THINKMCP_REPORTS_DIR": "/absolute/path/to/thinkmcp/reports"
      }
    }
  }
}
```

## Run as Remote HTTP Server

For cloud deployments or multi-client setups, run the Streamable HTTP transport:

```bash
python -m transport.http_transport --host 0.0.0.0 --port 8000
```

The MCP endpoint is at `http://your-host:8000/mcp`.

Then configure your client with type `http` and URL `http://your-host:8000/mcp`.

## Docker

```bash
docker build -t thinkmcp .
```

Run the Streamlit UI:

```bash
docker run -p 8501:8501 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e TAVILY_API_KEY="tvly-..." \
  -e GITHUB_TOKEN="ghp_..." \
  thinkmcp
```

Run the MCP HTTP server instead:

```bash
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e TAVILY_API_KEY="tvly-..." \
  thinkmcp \
  python -m transport.http_transport --port 8000
```

## Project Layout

```
thinkmcp/
├── server/
│   ├── mcp_server.py          # FastMCP server, all 13 tools registered
│   └── tools/
│       ├── research.py        # web_search, fetch_url, search_papers, search_code
│       ├── reasoning.py       # think, critique, plan
│       ├── memory.py          # remember, recall, list_memory
│       └── actions.py         # write_report, create_summary, compare
├── agent/
│   ├── thinking_agent.py      # agentic loop with adaptive thinking
│   ├── tool_executor.py       # in-process tool dispatch
│   └── trace_parser.py        # extracts thinking/tool blocks from responses
├── transport/
│   ├── stdio_transport.py     # stdio launcher (Claude Desktop)
│   └── http_transport.py      # Streamable HTTP launcher (remote)
├── app.py                     # Streamlit UI
├── requirements.txt
├── mcp_config.json            # template config for MCP clients
└── Dockerfile
```

## Reports

`write_report` saves markdown files to `THINKMCP_REPORTS_DIR` (default: `./reports/`). Files are timestamped: `report_my_topic_20240507_143022.md`.

## License

MIT
