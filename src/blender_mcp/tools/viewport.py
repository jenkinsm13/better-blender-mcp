"""Viewport tools for Blender MCP.

All tools in this module are wrapped by MainThreadMCP so they run on
Blender's main thread where bpy.context has full state (screen, area, etc.)
and bpy.ops calls work correctly.
"""

import os
import tempfile
import bpy
from blender_mcp.utils.responses import success, error

_HEADLESS_ERROR = error(
    "InvalidOperation",
    "No viewport available in --background mode",
)

_VALID_SHADING_MODES = {"SOLID", "WIREFRAME", "MATERIAL", "RENDERED"}

# Default 4-pack: classic CAD quad view + user's current perspective.
_DEFAULT_4PACK = ["TOP", "FRONT", "RIGHT", "PERSPECTIVE"]


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


def _stitch_2x2(paths, output_path, quad_res):
    """Stitch 4 PNG files into a 2x2 grid and save to output_path.

    Each image is resized to quad_res x quad_res before stitching so
    the final output is exactly 2*quad_res x 2*quad_res regardless of
    the original viewport dimensions.
    """
    import numpy as np

    tile_w, tile_h = quad_res, quad_res
    out_w, out_h = 2 * tile_w, 2 * tile_h
    out_pixels = np.zeros(out_h * out_w * 4, dtype=np.float32)
    out_2d = out_pixels.reshape(out_h, out_w, 4)

    # Blender pixel layout is bottom-up:
    #   row=1 (high y) = visual top row    -> views[0], views[1]
    #   row=0 (low y)  = visual bottom row -> views[2], views[3]
    positions = [(1, 0), (1, 1), (0, 0), (0, 1)]

    for path, (row, col) in zip(paths, positions):
        img = bpy.data.images.load(path)
        try:
            img.scale(tile_w, tile_h)
            px = np.empty(tile_w * tile_h * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            out_2d[
                row * tile_h : (row + 1) * tile_h,
                col * tile_w : (col + 1) * tile_w,
            ] = px.reshape(tile_h, tile_w, 4)
        finally:
            bpy.data.images.remove(img)

    out_img = bpy.data.images.new("_4pack_tmp", width=out_w, height=out_h, alpha=True)
    try:
        out_img.pixels.foreach_set(out_pixels)
        out_img.filepath_raw = output_path
        out_img.file_format = "PNG"
        out_img.save()
    finally:
        bpy.data.images.remove(out_img)


def register(mcp) -> None:
    """Register viewport tools."""

    @mcp.tool()
    def capture_viewport(output_path: str, resolution: int = 1920) -> dict:
        """Render the active 3D viewport to a PNG file at the given path.

        Returns the absolute path of the saved file.
        resolution sets the longer edge; aspect ratio is preserved.
        """
        window, area, space, region = _get_3d_view_context()
        if area is None:
            return _HEADLESS_ERROR

        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.screen.screenshot_area(filepath=output_path)

        if not os.path.exists(output_path):
            return error(
                "CaptureError", "screenshot_area ran but file was not created."
            )

        # Resize if needed (screenshot_area captures at native viewport size).
        img = bpy.data.images.load(output_path)
        try:
            w, h = img.size
            if max(w, h) > resolution:
                scale = resolution / max(w, h)
                img.scale(max(1, int(w * scale)), max(1, int(h * scale)))
                img.file_format = "PNG"
                img.save()
        finally:
            bpy.data.images.remove(img)

        return success(
            path=output_path,
            file_size_bytes=os.path.getsize(output_path),
        )

    @mcp.tool()
    def capture_viewport_4pack(output_path: str, resolution: int = 2048) -> dict:
        """Capture Top, Front, Right, and Perspective views stitched into a 2x2 grid.

        Each quadrant is rendered at resolution/2 using OpenGL viewport
        rendering, then combined into a single PNG.  The perspective quadrant
        preserves the user's current view angle.

        Layout: TOP (top-left), FRONT (top-right), RIGHT (bottom-left),
        PERSPECTIVE (bottom-right).
        """
        window, area, space, region = _get_3d_view_context()
        if area is None:
            return _HEADLESS_ERROR

        region_3d = space.region_3d
        scene = bpy.context.scene
        quad_res = resolution // 2

        # ── Save state ──────────────────────────────────────────────
        orig_rotation = region_3d.view_rotation.copy()
        orig_location = region_3d.view_location.copy()
        orig_distance = region_3d.view_distance
        orig_perspective = region_3d.view_perspective
        smooth = bpy.context.preferences.view.smooth_view

        # Disable smooth-view so view_axis snaps instantly.
        bpy.context.preferences.view.smooth_view = 0

        temp_dir = tempfile.gettempdir()
        temp_paths = []
        views = _DEFAULT_4PACK

        try:
            # Compute bounding box of all mesh objects for manual framing.
            from mathutils import Vector

            bbox_min = Vector((float("inf"),) * 3)
            bbox_max = Vector((float("-inf"),) * 3)
            for obj in scene.objects:
                if obj.type == "MESH":
                    for corner in obj.bound_box:
                        wc = obj.matrix_world @ Vector(corner)
                        bbox_min = Vector(min(a, b) for a, b in zip(bbox_min, wc))
                        bbox_max = Vector(max(a, b) for a, b in zip(bbox_max, wc))

            bbox_center = (bbox_min + bbox_max) / 2
            bbox_size = (bbox_max - bbox_min).length
            # Pad so geometry doesn't touch the edges.
            frame_distance = bbox_size * 1.2 if bbox_size > 0 else 10.0

            for i, view_name in enumerate(views):
                temp_path = os.path.join(temp_dir, f"_mcp_4pack_{i}.png")

                if view_name == "PERSPECTIVE":
                    # Restore original view for the perspective capture.
                    region_3d.view_rotation = orig_rotation.copy()
                    region_3d.view_location = orig_location.copy()
                    region_3d.view_distance = orig_distance
                    region_3d.view_perspective = "PERSP"
                else:
                    with bpy.context.temp_override(
                        window=window, area=area, region=region
                    ):
                        bpy.ops.view3d.view_axis(type=view_name)
                    # Directly set view center and zoom — instant, no deferred update.
                    region_3d.view_location = bbox_center.copy()
                    region_3d.view_distance = frame_distance

                # Force a redraw so the viewport reflects the new view state,
                # then capture the freshly drawn buffer with screenshot_area.
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
                with bpy.context.temp_override(window=window, area=area):
                    bpy.ops.screen.screenshot_area(filepath=temp_path)

                temp_paths.append(temp_path)

            # Stitch into 2x2 grid, resizing each to quad_res.
            _stitch_2x2(temp_paths, output_path, quad_res)

        finally:
            # ── Restore state ───────────────────────────────────────
            region_3d.view_rotation = orig_rotation
            region_3d.view_location = orig_location
            region_3d.view_distance = orig_distance
            region_3d.view_perspective = orig_perspective
            bpy.context.preferences.view.smooth_view = smooth

            # Cleanup temp files.
            for p in temp_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass

        return success(
            path=output_path,
            file_size_bytes=os.path.getsize(output_path),
            views=views,
            quadrant_resolution=quad_res,
        )

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
