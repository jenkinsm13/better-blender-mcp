"""Tool registration for all Blender MCP tools."""

import functools
import threading

from blender_mcp.tools import (
    scene,
    mesh,
    import_export,
    viewport,
    modifiers,
    transforms,
    project,
)

_MODULES = [scene, mesh, import_export, viewport, modifiers, transforms, project]


class MainThreadMCP:
    """Proxy that routes every @mcp.tool() call through the ExecutionQueue.

    bpy must run on Blender's main thread.  FastMCP handles HTTP on background
    threads.  This wrapper intercepts tool registration and wraps each function
    so it submits to the queue, blocks the HTTP thread on the future, and runs
    the real bpy code on the main thread via the timer callback.

    If the call is already on the main thread (e.g. during testing, or a tool
    calling another tool), it runs directly to avoid deadlock.
    """

    def __init__(self, mcp):
        self._mcp = mcp

    def tool(self, *args, **kwargs):
        """Return a decorator identical to mcp.tool() but main-thread-safe."""

        def decorator(fn):
            @functools.wraps(fn)
            def on_main_thread(*a, **kw):
                if threading.current_thread() is threading.main_thread():
                    return fn(*a, **kw)
                import blender_mcp

                q = blender_mcp._queue
                if q is None:
                    return fn(*a, **kw)
                future = q.submit(lambda: fn(*a, **kw))
                return future.result(timeout=120)

            return self._mcp.tool(*args, **kwargs)(on_main_thread)

        return decorator

    # Proxy everything else (e.g. mcp.resource()) to the real MCP.
    def __getattr__(self, name):
        return getattr(self._mcp, name)


def register_all_tools(mcp) -> None:
    """Register all tool modules with the MCP server.

    Wraps the MCP in MainThreadMCP so every tool automatically runs on
    Blender's main thread via the execution queue.
    """
    wrapped = MainThreadMCP(mcp)
    for module in _MODULES:
        module.register(wrapped)
