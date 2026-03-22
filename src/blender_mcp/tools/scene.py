"""Scene tools for Blender MCP."""

import bpy
import fnmatch
from blender_mcp.utils.responses import success, error
from blender_mcp.utils.naming import tile_grid_summary
from blender_mcp.utils.mesh_utils import bounding_box


def _collection_hierarchy(collection) -> dict:
    """Recursively build collection hierarchy as a nested dict."""
    return {
        "name": collection.name,
        "children": [_collection_hierarchy(c) for c in collection.children],
        "object_count": len(collection.objects),
    }


def register(mcp) -> None:
    """Register scene tools."""

    @mcp.tool()
    def get_scene_info() -> dict:
        """Scene overview with objects, collections, active object, frame range, and tile grid summary."""
        scene = bpy.context.scene

        objects = []
        all_names = []
        for obj in scene.objects:
            all_names.append(obj.name)
            entry = {"name": obj.name, "type": obj.type}
            if obj.type == "MESH" and obj.data is not None:
                entry["face_count"] = len(obj.data.polygons)
            else:
                entry["face_count"] = 0
            objects.append(entry)

        colls = _collection_hierarchy(scene.collection)

        active_name = None
        active = bpy.context.view_layer.objects.active
        if active is not None:
            active_name = active.name

        tile_info = tile_grid_summary(all_names)

        return success(
            objects=objects,
            collections=colls,
            active_object=active_name,
            frame_start=scene.frame_start,
            frame_end=scene.frame_end,
            frame_current=scene.frame_current,
            tile_grid=tile_info,
        )

    @mcp.tool()
    def get_object_info(object_name: str) -> dict:
        """Deep information on a single object: mesh stats, transforms, modifiers, materials, vertex groups, and bounding box."""
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        result: dict = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }

        if obj.type == "MESH" and obj.data is not None:
            mesh = obj.data
            result["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "faces": len(mesh.polygons),
            }
            result["bounding_box"] = bounding_box(obj)
            result["vertex_groups"] = [
                {
                    "name": vg.name,
                    "vertex_count": sum(
                        1
                        for v in mesh.vertices
                        if any(g.group == vg.index for g in v.groups)
                    ),
                }
                for vg in obj.vertex_groups
            ]
        else:
            result["mesh"] = None
            result["bounding_box"] = None
            result["vertex_groups"] = []

        result["modifiers"] = [
            {"name": mod.name, "type": mod.type} for mod in obj.modifiers
        ]
        result["materials"] = (
            [mat.name for mat in obj.data.materials if mat is not None]
            if obj.data is not None and hasattr(obj.data, "materials")
            else []
        )

        return success(**result)

    @mcp.tool()
    def list_objects(
        type_filter: str = "",
        collection: str = "",
        name_pattern: str = "",
    ) -> dict:
        """List scene objects with optional filters by type, collection, or name pattern (fnmatch)."""
        scene = bpy.context.scene

        # Build collection membership set if filtering by collection
        collection_objects: set[str] | None = None
        if collection:
            coll = bpy.data.collections.get(collection)
            if coll is None:
                return error(
                    "CollectionNotFound", f"Collection '{collection}' does not exist."
                )
            collection_objects = {obj.name for obj in coll.objects}

        objects = []
        for obj in scene.objects:
            if type_filter and obj.type != type_filter.upper():
                continue
            if collection_objects is not None and obj.name not in collection_objects:
                continue
            if name_pattern and not fnmatch.fnmatch(obj.name, name_pattern):
                continue

            face_count = 0
            if obj.type == "MESH" and obj.data is not None:
                face_count = len(obj.data.polygons)

            objects.append(
                {
                    "name": obj.name,
                    "type": obj.type,
                    "location": list(obj.location),
                    "face_count": face_count,
                }
            )

        return success(objects=objects, count=len(objects))

    @mcp.tool()
    def select_objects(
        names: list[str] | None = None,
        pattern: str = "",
        type_filter: str = "",
        collection: str = "",
    ) -> dict:
        """Deselect all objects, then select objects matching the given names, pattern, type, or collection."""
        # Deselect all
        for obj in bpy.context.scene.objects:
            obj.select_set(False)

        # Build collection membership set if needed
        collection_objects: set[str] | None = None
        if collection:
            coll = bpy.data.collections.get(collection)
            if coll is None:
                return error(
                    "CollectionNotFound", f"Collection '{collection}' does not exist."
                )
            collection_objects = {obj.name for obj in coll.objects}

        name_set = set(names) if names else None

        selected_count = 0
        for obj in bpy.context.scene.objects:
            if name_set is not None and obj.name not in name_set:
                continue
            if pattern and not fnmatch.fnmatch(obj.name, pattern):
                continue
            if type_filter and obj.type != type_filter.upper():
                continue
            if collection_objects is not None and obj.name not in collection_objects:
                continue

            obj.select_set(True)
            selected_count += 1

        return success(selected_count=selected_count)

    @mcp.tool()
    def create_collection(name: str, parent: str = "") -> dict:
        """Create a new collection, optionally nested under an existing parent collection."""
        if name in bpy.data.collections:
            return error("CollectionExists", f"Collection '{name}' already exists.")

        new_coll = bpy.data.collections.new(name)

        if parent:
            parent_coll = bpy.data.collections.get(parent)
            if parent_coll is None:
                return error(
                    "CollectionNotFound",
                    f"Parent collection '{parent}' does not exist.",
                )
            parent_coll.children.link(new_coll)
            path = f"{parent}/{name}"
        else:
            bpy.context.scene.collection.children.link(new_coll)
            path = name

        return success(name=name, path=path)

    @mcp.tool()
    def move_to_collection(object_names: list[str], collection_name: str) -> dict:
        """Unlink objects from all current collections and link them to the target collection."""
        target = bpy.data.collections.get(collection_name)
        if target is None:
            return error(
                "CollectionNotFound", f"Collection '{collection_name}' does not exist."
            )

        moved_count = 0
        for obj_name in object_names:
            obj = bpy.data.objects.get(obj_name)
            if obj is None:
                continue

            # Unlink from all collections that contain this object
            for coll in bpy.data.collections:
                if obj.name in coll.objects:
                    coll.objects.unlink(obj)

            # Also unlink from the scene root collection if present
            if obj.name in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.unlink(obj)

            target.objects.link(obj)
            moved_count += 1

        return success(moved_count=moved_count)

    @mcp.tool()
    def set_active_object(object_name: str) -> dict:
        """Set the active object in the current context by name."""
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        bpy.context.view_layer.objects.active = obj
        return success(name=obj.name)

    @mcp.tool()
    def delete_objects(
        object_names: list[str] | None = None,
        use_selection: bool = False,
    ) -> dict:
        """Delete named objects or the current selection. Returns deleted and remaining counts."""
        scene = bpy.context.scene

        if use_selection:
            to_delete = [obj for obj in scene.objects if obj.select_get()]
        elif object_names:
            to_delete = [
                bpy.data.objects[name]
                for name in object_names
                if name in bpy.data.objects
            ]
        else:
            to_delete = []

        deleted_count = len(to_delete)

        # Use bpy.ops after setting selection to the target objects
        # Override approach: directly use data.objects.remove for safety
        for obj in to_delete:
            bpy.data.objects.remove(obj, do_unlink=True)

        remaining_count = len(scene.objects)
        return success(deleted_count=deleted_count, remaining_count=remaining_count)
