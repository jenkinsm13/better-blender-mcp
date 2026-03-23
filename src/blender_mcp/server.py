"""FastMCP server for Blender MCP.

Creates the MCP server and registers all tools and resources.
Can run embedded in Blender (start_background) or standalone (main).
"""

from __future__ import annotations

import os
import sys
import threading

from mcp.server.fastmcp import FastMCP

DEFAULT_PORT = 8800


def create_mcp(port: int | None = None) -> FastMCP:
    """Build and configure a FastMCP instance."""
    if port is None:
        env = os.environ.get("BLENDER_MCP_PORT")
        port = int(env) if env else DEFAULT_PORT

    mcp = FastMCP(
        name="Blender",
        instructions=(
            "MCP server for Blender 5.1+. Provides tools for scene management, "
            "mesh operations, import/export, viewport control, modifiers, "
            "transforms, and project state.\n\n"
            "CRITICAL AGENT RULES:\n"
            "1. NEVER write scripts that batch multiple MCP tool calls. "
            "Call each tool INDIVIDUALLY, check the result, then call the next.\n"
            "2. NEVER alter object-level transforms on Tile_* objects.\n"
            "3. ALWAYS save the file after major operations with save_file().\n"
            "4. All mesh operations run on the main thread - long operations "
            "will block. This is expected.\n"
        ),
        stateless_http=True,
        json_response=True,
        port=port,
    )

    from blender_mcp.tools import register_all_tools
    from blender_mcp.resources import register_all_resources

    register_all_tools(mcp)
    register_all_resources(mcp)

    return mcp


_last_thread: threading.Thread | None = None
_last_mcp: FastMCP | None = None


def main(port: int | None = None) -> None:
    """Run server in foreground (standalone mode)."""
    mcp = create_mcp(port)
    mcp.run(transport="streamable-http")


def start_background(port: int | None = None) -> threading.Thread:
    """Start server on background thread (for embedding in Blender).

    Wraps stdout/stderr to add isatty() method for thread safety.
    Tracks _last_thread/_last_mcp to prevent double-start.
    """

    class _StdWrapper:
        def __init__(self, inner):
            self._inner = inner

        def write(self, s):
            return self._inner.write(s)

        def flush(self):
            if hasattr(self._inner, "flush"):
                self._inner.flush()

        def isatty(self):
            return False

    if not hasattr(sys.stdout, "isatty"):
        sys.stdout = _StdWrapper(sys.stdout)
    if not hasattr(sys.stderr, "isatty"):
        sys.stderr = _StdWrapper(sys.stderr)

    global _last_thread, _last_mcp

    if _last_thread and _last_thread.is_alive():
        existing_port = getattr(_last_mcp, "_port", port)
        if port is None or port == existing_port:
            print("MCP server already running, skipping start request.")
            return _last_thread
        try:
            _last_mcp.shutdown()
        except Exception:
            pass

    actual_port = port or DEFAULT_PORT
    mcp = create_mcp(actual_port)
    _last_mcp = mcp
    mcp._port = actual_port  # Track port for double-start detection

    def _run_server():
        try:
            mcp.run(transport="streamable-http")
        except Exception as exc:
            print(f"[BlenderMCP] Server crashed: {exc}", file=sys.stderr)
            import traceback

            traceback.print_exc(file=sys.stderr)

    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()
    _last_thread = thread

    print(f"Blender MCP server started on http://127.0.0.1:{actual_port}/mcp")
    return thread


if __name__ == "__main__":
    main()
