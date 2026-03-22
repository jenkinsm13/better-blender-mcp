"""Import/export tools for Blender MCP."""

import os

import bpy

from blender_mcp.utils.responses import success, error
from blender_mcp.utils.mesh_utils import bounding_box, is_identity_transform
from blender_mcp.utils.naming import tile_grid_summary


def _snapshot_objects() -> set:
    """Return a snapshot of all current bpy.data.objects."""
    return set(bpy.data.objects)


def _new_objects(before: set) -> list:
    """Return list of objects added since `before` snapshot was taken."""
    return list(set(bpy.data.objects) - before)


def _mesh_info(obj) -> dict:
    """Return vertex/face counts, bounding box, and identity_transform for a mesh object."""
    mesh = obj.data
    return {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "faces": len(mesh.polygons),
        "bounding_box": bounding_box(obj),
        "identity_transform": is_identity_transform(obj),
    }


def register(mcp) -> None:
    """Register import/export tools."""

    # ------------------------------------------------------------------
    # Importers
    # ------------------------------------------------------------------

    @mcp.tool()
    def import_ply(path: str) -> dict:
        """Import a PLY file into the current Blender scene."""
        if not os.path.exists(path):
            return error("FileError", f"File not found: {path}")
        before = _snapshot_objects()
        bpy.ops.wm.ply_import(filepath=path)
        new = _new_objects(before)
        if not new:
            return error("ImportError", "PLY import produced no new objects.")
        obj = new[0]
        return success(**_mesh_info(obj))

    @mcp.tool()
    def import_fbx(path: str) -> dict:
        """Import an FBX file into the current Blender scene."""
        if not os.path.exists(path):
            return error("FileError", f"File not found: {path}")
        before = _snapshot_objects()
        bpy.ops.import_scene.fbx(filepath=path)
        new = _new_objects(before)
        if not new:
            return error("ImportError", "FBX import produced no new objects.")
        obj = new[0]
        return success(**_mesh_info(obj))

    @mcp.tool()
    def import_obj(path: str) -> dict:
        """Import an OBJ file into the current Blender scene."""
        if not os.path.exists(path):
            return error("FileError", f"File not found: {path}")
        before = _snapshot_objects()
        bpy.ops.wm.obj_import(filepath=path)
        new = _new_objects(before)
        if not new:
            return error("ImportError", "OBJ import produced no new objects.")
        obj = new[0]
        return success(**_mesh_info(obj))

    # ------------------------------------------------------------------
    # Exporters
    # ------------------------------------------------------------------

    @mcp.tool()
    def export_fbx(
        path: str,
        object_name: str = "",
        apply_scale_options: str = "FBX_SCALE_NONE",
        axis_forward: str = "-Z",
        axis_up: str = "Y",
    ) -> dict:
        """Export scene or a single object to FBX with game-engine defaults."""
        kwargs = dict(
            filepath=path,
            apply_scale_options=apply_scale_options,
            axis_forward=axis_forward,
            axis_up=axis_up,
            use_tspace=True,
            mesh_smooth_type="OFF",
        )
        if object_name:
            if object_name not in bpy.data.objects:
                return error("ObjectError", f"Object not found: {object_name}")
            # Deselect all, select the target object
            bpy.ops.object.select_all(action="DESELECT")
            obj = bpy.data.objects[object_name]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            kwargs["use_selection"] = True
        bpy.ops.export_scene.fbx(**kwargs)
        return success(path=path, file_size_bytes=os.path.getsize(path))

    @mcp.tool()
    def export_obj(path: str, object_name: str = "") -> dict:
        """Export scene or a single object to OBJ (Metashape round-trip defaults)."""
        kwargs = dict(
            filepath=path,
            forward_axis="NEGATIVE_Z",
            up_axis="Y",
            export_uv=True,
            export_normals=True,
        )
        if object_name:
            if object_name not in bpy.data.objects:
                return error("ObjectError", f"Object not found: {object_name}")
            bpy.ops.object.select_all(action="DESELECT")
            obj = bpy.data.objects[object_name]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            kwargs["export_selected_objects"] = True
        bpy.ops.wm.obj_export(**kwargs)
        return success(path=path, file_size_bytes=os.path.getsize(path))

    @mcp.tool()
    def export_ply(path: str, object_name: str = "") -> dict:
        """Export scene or a single object to PLY."""
        kwargs = dict(filepath=path)
        if object_name:
            if object_name not in bpy.data.objects:
                return error("ObjectError", f"Object not found: {object_name}")
            bpy.ops.object.select_all(action="DESELECT")
            obj = bpy.data.objects[object_name]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            kwargs["export_selected_objects"] = True
        bpy.ops.wm.ply_export(**kwargs)
        return success(path=path, file_size_bytes=os.path.getsize(path))

    # ------------------------------------------------------------------
    # Stubs (platform-specific formats implemented on Windows PC)
    # ------------------------------------------------------------------

    @mcp.tool()
    def export_kn5(path: str) -> dict:
        """Export to KN5 format (Assetto Corsa). Not yet implemented on this platform."""
        return error(
            "NotImplemented",
            "KN5 export not yet implemented. Implementation pending on Windows PC.",
        )

    @mcp.tool()
    def export_kpm(path: str) -> dict:
        """Export to KPM format (Assetto Corsa physics mesh). Not yet implemented on this platform."""
        return error(
            "NotImplemented",
            "KPM export not yet implemented. Implementation pending on Windows PC.",
        )

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    @mcp.tool()
    def batch_import(directory: str, format: str = "ply") -> dict:
        """Import all files of the given format from a directory."""
        if not os.path.isdir(directory):
            return error("FileError", f"Directory not found: {directory}")

        ext = format.lower().lstrip(".")
        files = sorted(
            f for f in os.listdir(directory) if f.lower().endswith(f".{ext}")
        )
        if not files:
            return error(
                "FileError",
                f"No .{ext} files found in directory: {directory}",
            )

        # Map format -> import operator
        importers = {
            "ply": lambda p: bpy.ops.wm.ply_import(filepath=p),
            "fbx": lambda p: bpy.ops.import_scene.fbx(filepath=p),
            "obj": lambda p: bpy.ops.wm.obj_import(filepath=p),
        }
        if ext not in importers:
            return error("FormatError", f"Unsupported batch import format: {ext}")

        importer = importers[ext]
        tiles = []
        all_names = []

        for filename in files:
            filepath = os.path.join(directory, filename)
            stem = os.path.splitext(filename)[0]
            before = _snapshot_objects()
            importer(filepath)
            new = _new_objects(before)
            if new:
                obj = new[0]
                # Rename to stem derived from filename
                obj.name = stem
                info = _mesh_info(obj)
                tiles.append(
                    {
                        "name": info["name"],
                        "vertices": info["vertices"],
                        "faces": info["faces"],
                        "identity_transform": info["identity_transform"],
                    }
                )
                all_names.append(obj.name)

        grid = tile_grid_summary(all_names)
        return success(
            tiles=tiles,
            total_objects=len(tiles),
            tile_grid=grid,
        )

    @mcp.tool()
    def batch_export(
        directory: str,
        format: str = "fbx",
        object_names: list[str] | None = None,
    ) -> dict:
        """Export objects individually to files in the given directory."""
        if not os.path.isdir(directory):
            return error("FileError", f"Directory not found: {directory}")

        ext = format.lower().lstrip(".")

        if object_names is None:
            object_names = [obj.name for obj in bpy.data.objects if obj.type == "MESH"]

        if not object_names:
            return error("ExportError", "No mesh objects to export.")

        # Map format -> export function (path, object_name) -> None
        def _do_fbx(path, name):
            bpy.ops.object.select_all(action="DESELECT")
            obj = bpy.data.objects[name]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.export_scene.fbx(
                filepath=path,
                use_selection=True,
                apply_scale_options="FBX_SCALE_NONE",
                axis_forward="-Z",
                axis_up="Y",
                use_tspace=True,
                mesh_smooth_type="OFF",
            )

        def _do_obj(path, name):
            bpy.ops.object.select_all(action="DESELECT")
            obj = bpy.data.objects[name]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.wm.obj_export(
                filepath=path,
                forward_axis="NEGATIVE_Z",
                up_axis="Y",
                export_uv=True,
                export_normals=True,
                export_selected_objects=True,
            )

        def _do_ply(path, name):
            bpy.ops.object.select_all(action="DESELECT")
            obj = bpy.data.objects[name]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.wm.ply_export(
                filepath=path,
                export_selected_objects=True,
            )

        exporters = {
            "fbx": _do_fbx,
            "obj": _do_obj,
            "ply": _do_ply,
        }
        if ext not in exporters:
            return error("FormatError", f"Unsupported batch export format: {ext}")

        exporter = exporters[ext]
        exports = []

        for name in object_names:
            if name not in bpy.data.objects:
                continue
            out_path = os.path.join(directory, f"{name}.{ext}")
            exporter(out_path, name)
            exports.append(
                {
                    "name": name,
                    "path": out_path,
                    "file_size_bytes": os.path.getsize(out_path),
                }
            )

        return success(exports=exports, total_exports=len(exports))
