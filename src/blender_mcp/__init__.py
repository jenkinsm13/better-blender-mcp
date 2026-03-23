"""Blender MCP addon - embedded FastMCP server for Claude Code integration.

Registers a sidebar panel in 3D Viewport for server control.
Timer callback drains the execution queue on the main thread.
"""

bl_info = {
    "name": "Blender MCP",
    "author": "Mike Jenkins",
    "version": (0, 1, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Embedded MCP server for Claude Code integration",
    "category": "Interface",
}

_server_thread = None
_queue = None


def get_queue():
    """Return the active ExecutionQueue, or None if server is not running."""
    return _queue


def _purge_submodules():
    """Remove all blender_mcp.* submodules from sys.modules.

    This forces Python to reimport from disk on the next ``from blender_mcp.x
    import y``, ensuring Stop→Start always picks up code changes without
    restarting Blender.  The top-level ``blender_mcp`` package is kept because
    it owns the addon registration and timer state.
    """
    import sys

    to_purge = [k for k in sys.modules if k.startswith("blender_mcp.")]
    for k in to_purge:
        del sys.modules[k]


def _timer_callback():
    """Drain execution queue on main thread. Called by bpy.app.timers."""
    if _queue is not None:
        _queue.drain()
    return 0.05  # Repeat every 50ms


def _register_blender_classes():
    """Register Blender UI classes. Only called inside Blender."""
    import bpy
    from bpy.props import IntProperty

    class BLENDERMCP_OT_start(bpy.types.Operator):
        bl_idname = "blendermcp.start"
        bl_label = "Start MCP Server"

        def execute(self, context):
            import time

            global _server_thread, _queue

            # If a previous server is still alive, shut it down first.
            try:
                from blender_mcp.server import _last_mcp, _last_thread

                if _last_mcp:
                    _last_mcp.shutdown()
                if _last_thread and _last_thread.is_alive():
                    _last_thread.join(timeout=2.0)
            except Exception:
                pass

            # Purge cached submodules AFTER the old server is dead so we
            # don't yank modules out from under a running thread.
            _purge_submodules()
            time.sleep(0.3)  # let the OS release the port

            from blender_mcp.queue import ExecutionQueue
            from blender_mcp.server import start_background

            prefs = context.scene.blendermcp
            _queue = ExecutionQueue()
            _server_thread = start_background(port=prefs.port)

            if not bpy.app.timers.is_registered(_timer_callback):
                bpy.app.timers.register(_timer_callback, persistent=True)

            return {"FINISHED"}

    class BLENDERMCP_OT_stop(bpy.types.Operator):
        bl_idname = "blendermcp.stop"
        bl_label = "Stop MCP Server"

        def execute(self, context):
            global _server_thread, _queue
            from blender_mcp.server import _last_mcp

            if _last_mcp:
                try:
                    _last_mcp.shutdown()
                except Exception:
                    pass

            if bpy.app.timers.is_registered(_timer_callback):
                bpy.app.timers.unregister(_timer_callback)

            _server_thread = None
            _queue = None
            return {"FINISHED"}

    class BLENDERMCP_PT_panel(bpy.types.Panel):
        bl_label = "BlenderMCP"
        bl_idname = "BLENDERMCP_PT_panel"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "BlenderMCP"

        def draw(self, context):
            layout = self.layout
            prefs = context.scene.blendermcp

            is_running = _server_thread is not None and _server_thread.is_alive()

            row = layout.row()
            row.prop(prefs, "port")

            if is_running:
                layout.label(text="Status: Running", icon="PLAY")
                layout.operator("blendermcp.stop", icon="PAUSE")
            else:
                layout.label(text="Status: Stopped", icon="PAUSE")
                layout.operator("blendermcp.start", icon="PLAY")

    class BlenderMCPProperties(bpy.types.PropertyGroup):
        port: IntProperty(
            name="Port",
            default=8800,
            min=1024,
            max=65535,
        )

    return (
        BlenderMCPProperties,
        BLENDERMCP_OT_start,
        BLENDERMCP_OT_stop,
        BLENDERMCP_PT_panel,
    )


# Store classes at module level after registration
_classes = None


def register():
    """Register addon with Blender."""
    global _classes
    import bpy

    _classes = _register_blender_classes()
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blendermcp = bpy.props.PointerProperty(type=_classes[0])


def unregister():
    """Unregister addon from Blender."""
    global _server_thread, _queue, _classes
    import bpy

    if bpy.app.timers.is_registered(_timer_callback):
        bpy.app.timers.unregister(_timer_callback)

    from blender_mcp.server import _last_mcp

    if _last_mcp:
        try:
            _last_mcp.shutdown()
        except Exception:
            pass

    _server_thread = None
    _queue = None

    if hasattr(bpy.types.Scene, "blendermcp"):
        del bpy.types.Scene.blendermcp

    if _classes:
        for cls in reversed(_classes):
            bpy.utils.unregister_class(cls)
        _classes = None
