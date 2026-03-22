"""Viewport tools for Blender MCP."""

import os
import bpy
from blender_mcp.utils.responses import success, error

_HEADLESS_ERROR = error(
    "InvalidOperation",
    "No viewport available in --background mode",
)

_VALID_SHADING_MODES = {"SOLID", "WIREFRAME", "MATERIAL", "RENDERED"}


def _get_3d_view_context():
    """Return (window, area, space, region) for the first VIEW_3D found, or Nones.

    Works from any thread by walking bpy.context.window_manager.windows
    (bpy.context.screen is None on background threads).
    """
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = None
                region = None
                for s in area.spaces:
                    if s.type == "VIEW_3D":
                        space = s
                        break
                for r in area.regions:
                    if r.type == "WINDOW":
                        region = r
                        break
                if space:
                    return window, area, space, region
    return None, None, None, None


def _capture_on_main_thread(output_path: str, resolution: int) -> dict:
    """Take a viewport screenshot on the main thread.

    Uses bpy.ops.screen.screenshot_area (the same approach as the community
    Blender MCP).  Must run on the main thread where bpy.context has full
    state — call via ExecutionQueue.submit().
    """
    # Find VIEW_3D — on main thread bpy.context.screen is available but we
    # use the same window_manager walk for consistency.
    window, area, space, region = _get_3d_view_context()
    if area is None:
        return _HEADLESS_ERROR

    with bpy.context.temp_override(window=window, area=area):
        bpy.ops.screen.screenshot_area(filepath=output_path)

    if not os.path.exists(output_path):
        return error("CaptureError", "screenshot_area ran but file was not created.")

    # Resize if needed (screenshot_area captures at native viewport size).
    img = bpy.data.images.load(output_path)
    try:
        w, h = img.size
        if max(w, h) > resolution:
            scale = resolution / max(w, h)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img.scale(new_w, new_h)
            img.file_format = "PNG"
            img.save()
    finally:
        bpy.data.images.remove(img)

    return success(
        path=output_path,
        file_size_bytes=os.path.getsize(output_path),
    )


def register(mcp) -> None:
    """Register viewport tools."""

    @mcp.tool()
    def capture_viewport(output_path: str, resolution: int = 1920) -> dict:
        """Render the active 3D viewport to a PNG file at the given path.

        Returns the absolute path of the saved file.
        resolution sets the longer edge; aspect ratio is preserved.
        """
        import concurrent.futures
        import blender_mcp

        q = blender_mcp._queue
        if q is None:
            return error(
                "ServerError",
                "Execution queue not available — is the server running?",
            )

        # Route through queue so the capture runs on the main thread where
        # bpy.context has full state and operators work.
        future = q.submit(lambda: _capture_on_main_thread(output_path, resolution))
        try:
            return future.result(timeout=15)
        except concurrent.futures.TimeoutError:
            return error("CaptureError", "Viewport capture timed out after 15 s.")

    @mcp.tool()
    def set_viewport_shading(mode: str = "SOLID") -> dict:
        """Set the shading mode of the active 3D viewport.

        mode must be one of: SOLID, WIREFRAME, MATERIAL, RENDERED.
        """
        mode = mode.upper()
        if mode not in _VALID_SHADING_MODES:
            return error(
                "InvalidArgument",
                f"mode must be one of {sorted(_VALID_SHADING_MODES)}, got '{mode}'.",
            )

        window, area, space, region = _get_3d_view_context()
        if area is None:
            return _HEADLESS_ERROR

        space.shading.type = mode
        return success(mode=mode)

    @mcp.tool()
    def frame_objects(object_names: list[str] | None = None) -> dict:
        """Pan and zoom the active 3D viewport to frame the named objects.

        If object_names is None or empty, all scene objects are framed.
        Returns the count of objects that were selected and framed.
        """
        window, area, space, region = _get_3d_view_context()
        if area is None:
            return _HEADLESS_ERROR

        # Deselect all
        for obj in bpy.context.scene.objects:
            obj.select_set(False)

        if object_names:
            framed = []
            for name in object_names:
                obj = bpy.data.objects.get(name)
                if obj is not None:
                    obj.select_set(True)
                    framed.append(name)
            framed_count = len(framed)
        else:
            for obj in bpy.context.scene.objects:
                obj.select_set(True)
            framed_count = len(bpy.context.scene.objects)

        if region is None:
            return error(
                "InvalidOperation", "Could not find WINDOW region in VIEW_3D area."
            )

        with bpy.context.temp_override(
            window=window, area=area, region=region, space_data=space
        ):
            bpy.ops.view3d.view_selected()

        return success(framed_count=framed_count)

    @mcp.tool()
    def set_viewport_overlay(
        wireframe: bool | None = None,
        face_orientation: bool | None = None,
        vertex_groups: bool | None = None,
    ) -> dict:
        """Toggle overlay options on the active 3D viewport.

        Only properties passed as non-None are changed.
        Returns the resulting state of all three overlay flags.
        """
        window, area, space, region = _get_3d_view_context()
        if area is None:
            return _HEADLESS_ERROR

        overlay = space.overlay
        if wireframe is not None:
            overlay.show_wireframes = wireframe
        if face_orientation is not None:
            overlay.show_face_orientation = face_orientation
        if vertex_groups is not None:
            overlay.show_vertex_groups_weights = vertex_groups

        return success(
            wireframe=overlay.show_wireframes,
            face_orientation=overlay.show_face_orientation,
            vertex_groups=overlay.show_vertex_groups_weights,
        )
