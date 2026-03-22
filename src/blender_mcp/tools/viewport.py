"""Viewport tools for Blender MCP."""

import bpy
from blender_mcp.utils.responses import success, error

_HEADLESS_ERROR = error(
    "InvalidOperation",
    "No viewport available in --background mode",
)

_VALID_SHADING_MODES = {"SOLID", "WIREFRAME", "MATERIAL", "RENDERED"}


def _get_3d_view_space():
    """Return the first SpaceView3D found across all areas, or None."""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    return area, space
    return None, None


def register(mcp) -> None:
    """Register viewport tools."""

    @mcp.tool()
    def capture_viewport(output_path: str, resolution: int = 1920) -> dict:
        """Render the active 3D viewport to a PNG file at the given path.

        Returns the absolute path of the saved file.
        resolution sets the longer edge; aspect ratio is preserved from the scene render settings.
        """
        if not bpy.context.screen:
            return _HEADLESS_ERROR

        area, space = _get_3d_view_space()
        if area is None:
            return error(
                "InvalidOperation", "No VIEW_3D area found in the current screen."
            )

        # Save scene render resolution so we can restore it
        scene = bpy.context.scene
        orig_x = scene.render.resolution_x
        orig_y = scene.render.resolution_y
        orig_pct = scene.render.resolution_percentage

        # Set resolution
        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100

        try:
            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=output_path)
        except Exception as exc:
            return error("CaptureError", str(exc))
        finally:
            scene.render.resolution_x = orig_x
            scene.render.resolution_y = orig_y
            scene.render.resolution_percentage = orig_pct

        return success(path=output_path)

    @mcp.tool()
    def set_viewport_shading(mode: str = "SOLID") -> dict:
        """Set the shading mode of the active 3D viewport.

        mode must be one of: SOLID, WIREFRAME, MATERIAL, RENDERED.
        """
        if not bpy.context.screen:
            return _HEADLESS_ERROR

        mode = mode.upper()
        if mode not in _VALID_SHADING_MODES:
            return error(
                "InvalidArgument",
                f"mode must be one of {sorted(_VALID_SHADING_MODES)}, got '{mode}'.",
            )

        area, space = _get_3d_view_space()
        if area is None:
            return error(
                "InvalidOperation", "No VIEW_3D area found in the current screen."
            )

        space.shading.type = mode
        return success(mode=mode)

    @mcp.tool()
    def frame_objects(object_names: list[str] | None = None) -> dict:
        """Pan and zoom the active 3D viewport to frame the named objects.

        If object_names is None or empty, all scene objects are framed.
        Returns the count of objects that were selected and framed.
        """
        if not bpy.context.screen:
            return _HEADLESS_ERROR

        area, space = _get_3d_view_space()
        if area is None:
            return error(
                "InvalidOperation", "No VIEW_3D area found in the current screen."
            )

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

        region = None
        for r in area.regions:
            if r.type == "WINDOW":
                region = r
                break

        if region is None:
            return error(
                "InvalidOperation", "Could not find WINDOW region in VIEW_3D area."
            )

        with bpy.context.temp_override(area=area, region=region, space_data=space):
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
        if not bpy.context.screen:
            return _HEADLESS_ERROR

        area, space = _get_3d_view_space()
        if area is None:
            return error(
                "InvalidOperation", "No VIEW_3D area found in the current screen."
            )

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
