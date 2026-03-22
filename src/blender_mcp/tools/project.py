"""Project tools for Blender MCP."""

import os
import io
import contextlib

import bpy

from blender_mcp.utils.responses import success, error


def register(mcp) -> None:
    """Register project tools."""

    @mcp.tool()
    def save_file() -> dict:
        """Save the current .blend file to disk."""
        filepath = bpy.data.filepath
        if not filepath:
            return error(
                "FileError", "File has never been saved. Use Blender to save first."
            )
        bpy.ops.wm.save_mainfile()
        return success(path=filepath, file_size_bytes=os.path.getsize(filepath))

    @mcp.tool()
    def open_file(path: str) -> dict:
        """Open a .blend file from disk."""
        if not os.path.exists(path):
            return error("FileError", f"File not found: {path}")
        bpy.ops.wm.open_mainfile(filepath=path)
        collections = [c.name for c in bpy.data.collections]
        return success(
            path=path,
            object_count=len(bpy.data.objects),
            collections=collections,
        )

    @mcp.tool()
    def get_project_state() -> dict:
        """Return current project state including filepath, dirty flag, and Blender version."""
        return success(
            filepath=bpy.data.filepath,
            is_dirty=bpy.data.is_dirty,
            blender_version=bpy.app.version_string,
            undo_steps=bpy.context.preferences.edit.undo_steps,
        )

    @mcp.tool()
    def execute_python(code: str) -> dict:
        """Execute arbitrary Python code in the Blender environment. Captures stdout and stderr."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        try:
            with (
                contextlib.redirect_stdout(stdout_buf),
                contextlib.redirect_stderr(stderr_buf),
            ):
                exec(code, {"__builtins__": __builtins__, "bpy": bpy})  # noqa: S102
        except Exception as exc:  # noqa: BLE001
            stderr_buf.write(f"{type(exc).__name__}: {exc}")
        return success(stdout=stdout_buf.getvalue(), stderr=stderr_buf.getvalue())
