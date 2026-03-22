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

    Works from timer context where bpy.context.screen is None by walking
    bpy.context.window_manager.windows instead.
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


def _make_capture_pending(output_path: str, resolution: int, area):
    """Return a PendingResult that captures the viewport via a POST_PIXEL draw handler.

    Called on the main thread (from queue.drain).  The draw handler fires during
    the very next Blender draw cycle when GPU context IS active, reads the
    framebuffer, writes a PNG, then resolves the future the HTTP thread is
    waiting on.
    """
    from blender_mcp.queue import PendingResult

    def setup_capture(future) -> None:
        _done = [False]  # guard: only fire once

        def draw_callback() -> None:
            if _done[0]:
                return
            _done[0] = True

            # Remove handler immediately to avoid repeated firing.
            try:
                bpy.types.SpaceView3D.draw_handler_remove(_handle[0], "WINDOW")
            except Exception:
                pass

            try:
                import gpu
                import numpy as np

                w, h = area.width, area.height
                fb = gpu.state.active_framebuffer_get()
                buf = fb.read_color(area.x, area.y, w, h, 4, 0, "UBYTE")

                # Preserve aspect ratio when scaling.
                if w >= h:
                    new_w = resolution
                    new_h = max(1, int(resolution * h / w))
                else:
                    new_h = resolution
                    new_w = max(1, int(resolution * w / h))

                img = bpy.data.images.new(
                    "_mcp_capture_tmp", width=w, height=h, alpha=True
                )
                try:
                    pixels_f32 = (
                        np.frombuffer(bytes(buf), dtype=np.uint8).astype(np.float32)
                        / 255.0
                    )
                    img.pixels.foreach_set(pixels_f32)
                    if (new_w, new_h) != (w, h):
                        img.scale(new_w, new_h)
                    img.filepath_raw = output_path
                    img.file_format = "PNG"
                    img.save()
                finally:
                    bpy.data.images.remove(img)

                if os.path.exists(output_path):
                    future.set_result(
                        success(
                            path=output_path,
                            file_size_bytes=os.path.getsize(output_path),
                        )
                    )
                else:
                    future.set_result(
                        error(
                            "CaptureError", "Draw handler ran but file was not created."
                        )
                    )
            except Exception as exc:
                future.set_result(error("CaptureError", str(exc)))

        _handle = [None]
        _handle[0] = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback, (), "WINDOW", "POST_PIXEL"
        )
        area.tag_redraw()

    return PendingResult(setup_capture)


def register(mcp) -> None:
    """Register viewport tools."""

    @mcp.tool()
    def capture_viewport(output_path: str, resolution: int = 1920) -> dict:
        """Capture the active 3D viewport to a PNG file.

        Uses a GPU POST_PIXEL draw handler — works even though bpy operators
        cannot be called from background threads.  resolution sets the longer
        edge; viewport aspect ratio is preserved.  Returns the absolute path
        and file size of the saved PNG.
        """
        import concurrent.futures
        from blender_mcp import get_queue

        q = get_queue()
        if q is None:
            return error(
                "ServerError", "Execution queue not available — is the server running?"
            )

        window, area, space, region = _get_3d_view_context()
        if area is None:
            return _HEADLESS_ERROR

        # Submit the draw-handler setup to the main thread via the queue.
        # _make_capture_pending returns a PendingResult; drain() will call
        # setup_fn(future) which registers the handler and tags a redraw.
        # This HTTP thread then blocks on future.result() until the next
        # draw cycle resolves it.
        future = q.submit(lambda: _make_capture_pending(output_path, resolution, area))
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
