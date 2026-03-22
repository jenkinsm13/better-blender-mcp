"""Stdio-to-HTTP proxy for Blender MCP server.

Bridges Claude Code (stdio) to the Blender HTTP server.
24-hour timeout for long Blender operations.
"""

from __future__ import annotations

import os

from fastmcp import Client
from fastmcp.server import create_proxy

_TIMEOUT_SECONDS = 86400  # 24 hours

port = int(os.environ.get("BLENDER_MCP_PORT", "8800"))
url = f"http://127.0.0.1:{port}/mcp"

client = Client(url, timeout=_TIMEOUT_SECONDS)
proxy = create_proxy(client, name="Blender")


def main() -> None:
    """Entry point for uv run blender-mcp."""
    proxy.run(transport="stdio")


if __name__ == "__main__":
    main()
