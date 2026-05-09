"""
stdio transport launcher — for Claude Desktop and local CLI use.

Usage:
    python -m transport.stdio_transport

This is equivalent to:
    python server/mcp_server.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from server.mcp_server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
