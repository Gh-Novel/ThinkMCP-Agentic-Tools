"""
Streamable HTTP transport launcher — for remote / cloud deployments.

Usage:
    python -m transport.http_transport [--host HOST] [--port PORT]

Exposes the MCP server at:
    GET  /mcp     → Server-Sent Events stream
    POST /mcp     → send messages
    DELETE /mcp   → terminate session
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from server.mcp_server import mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinkMCP Streamable HTTP server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    args = parser.parse_args()

    print(f"[ThinkMCP HTTP] Listening on http://{args.host}:{args.port}/mcp", file=sys.stderr)
    mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
