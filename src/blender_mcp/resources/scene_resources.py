import bpy
from blender_mcp.utils.naming import tile_grid_summary
from blender_mcp.utils.mesh_utils import bounding_box


def register(mcp) -> None:
    """Register scene resources."""

    @mcp.resource("blender://scene/info")
    def scene_info() -> dict:
        """Current scene overview."""
        scene = bpy.context.scene
        objects = []
        for obj in scene.objects:
            info = {"name": obj.name, "type": obj.type}
            if obj.type == "MESH" and obj.data:
                info["faces"] = len(obj.data.polygons)
            objects.append(info)
        return {
            "name": scene.name,
            "object_count": len(scene.objects),
            "objects": objects,
            "active_object": scene.objects.active.name
            if scene.objects.active
            else None,
            "frame_range": [scene.frame_start, scene.frame_end],
        }

    @mcp.resource("blender://scene/objects")
    def scene_objects() -> list:
        """Full object list with types and basic stats."""
        result = []
        for obj in bpy.context.scene.objects:
            info = {
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
            }
            if obj.type == "MESH" and obj.data:
                info["face_count"] = len(obj.data.polygons)
                info["vertex_count"] = len(obj.data.vertices)
            else:
                info["face_count"] = 0
                info["vertex_count"] = 0
            result.append(info)
        return result

    @mcp.resource("blender://object/{name}")
    def object_info(name: str) -> dict:
        """Detailed info for a specific object."""
        obj = bpy.data.objects.get(name)
        if not obj:
            return {"error": "ObjectNotFound", "message": f"No object named '{name}'"}

        info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
            "materials": [m.name if m else None for m in obj.data.materials]
            if hasattr(obj.data, "materials")
            else [],
        }

        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            info["vertices"] = len(mesh.vertices)
            info["edges"] = len(mesh.edges)
            info["faces"] = len(mesh.polygons)
            info["vertex_groups"] = [
                {"name": vg.name, "index": vg.index} for vg in obj.vertex_groups
            ]
            info["bounding_box"] = bounding_box(obj)
            info["has_uv"] = len(mesh.uv_layers) > 0
            info["has_vertex_colors"] = len(mesh.color_attributes) > 0

        return info

    @mcp.resource("blender://project/state")
    def project_state() -> dict:
        """File path, modified status, Blender version."""
        return {
            "filepath": bpy.data.filepath or "(unsaved)",
            "is_dirty": bpy.data.is_dirty,
            "blender_version": bpy.app.version_string,
        }

    @mcp.resource("blender://tiles/grid")
    def tiles_grid() -> dict:
        """Tile grid summary - loaded Tile_X-Y objects, gaps, coverage."""
        names = [obj.name for obj in bpy.context.scene.objects]
        return tile_grid_summary(names)
