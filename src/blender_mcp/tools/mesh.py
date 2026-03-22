"""Mesh tools for Blender MCP.

Core terrain processing tools: mesh analysis, decimation, cleanup,
boolean operations, surface classification, and canopy envelope removal.
"""

import math
import bpy
import bmesh
from blender_mcp.utils.responses import success, error
from blender_mcp.utils.mesh_utils import bounding_box, check_tile_transform


def _ensure_object_mode():
    """Return to object mode if currently in edit mode."""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _get_mesh_object(object_name: str):
    """Look up an object by name and verify it is a mesh.

    Returns (obj, None) on success or (None, error_dict) on failure.
    """
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return None, error("ObjectNotFound", f"Object '{object_name}' does not exist.")
    if obj.type != "MESH":
        return None, error(
            "NotAMesh", f"Object '{object_name}' is type '{obj.type}', not MESH."
        )
    return obj, None


def _set_active_and_select(obj):
    """Deselect all, then select and activate *obj*."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def register(mcp) -> None:
    """Register mesh tools."""

    # ------------------------------------------------------------------
    # 1. get_mesh_stats
    # ------------------------------------------------------------------
    @mcp.tool()
    def get_mesh_stats(object_name: str) -> dict:
        """Return detailed mesh statistics: vertex/edge/face counts, bounding box, UV layers, vertex colors, and vertex groups."""
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        mesh = obj.data
        return success(
            vertices=len(mesh.vertices),
            edges=len(mesh.edges),
            faces=len(mesh.polygons),
            bounding_box=bounding_box(obj),
            has_uv=len(mesh.uv_layers) > 0,
            has_vertex_colors=len(mesh.color_attributes) > 0,
            vertex_groups=[vg.name for vg in obj.vertex_groups],
        )

    # ------------------------------------------------------------------
    # 2. decimate_mesh
    # ------------------------------------------------------------------
    @mcp.tool()
    def decimate_mesh(
        object_name: str,
        ratio: float = 0.5,
        target_count: int = 0,
        method: str = "ratio",
    ) -> dict:
        """Decimate a mesh by ratio, target face count, or planar angle. Applies the modifier immediately."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        before_faces = len(obj.data.polygons)
        _set_active_and_select(obj)

        mod = obj.modifiers.new(name="MCP_Decimate", type="DECIMATE")

        if method == "planar":
            mod.decimate_type = "DISSOLVE"
            mod.angle_limit = ratio  # ratio re-used as angle threshold in radians
        elif method == "target" and target_count > 0:
            if before_faces > 0:
                computed_ratio = min(max(target_count / before_faces, 0.0), 1.0)
            else:
                computed_ratio = 1.0
            mod.decimate_type = "COLLAPSE"
            mod.ratio = computed_ratio
        else:
            mod.decimate_type = "COLLAPSE"
            mod.ratio = min(max(ratio, 0.0), 1.0)

        bpy.ops.object.modifier_apply(modifier=mod.name)
        after_faces = len(obj.data.polygons)

        reduction = 0.0
        if before_faces > 0:
            reduction = round((1.0 - after_faces / before_faces) * 100, 2)

        return success(
            before_faces=before_faces,
            after_faces=after_faces,
            reduction_percent=reduction,
        )

    # ------------------------------------------------------------------
    # 3. separate_loose
    # ------------------------------------------------------------------
    @mcp.tool()
    def separate_loose(object_name: str, keep_largest: bool = True) -> dict:
        """Separate loose mesh parts into individual objects. Optionally keep only the largest part."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        _set_active_and_select(obj)
        base_name = obj.name

        # Enter edit mode, select all, separate
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.mode_set(mode="OBJECT")

        # Find all resulting objects (Blender appends .001, .002, etc.)
        parts = [
            o
            for o in bpy.data.objects
            if o.type == "MESH"
            and (o.name == base_name or o.name.startswith(base_name + "."))
        ]

        parts_found = len(parts)

        if keep_largest and parts_found > 1:
            # Find the part with the most faces
            largest = max(parts, key=lambda o: len(o.data.polygons))
            deleted_names = []
            for part in parts:
                if part is not largest:
                    deleted_names.append(part.name)
                    bpy.data.objects.remove(part, do_unlink=True)

            return success(
                parts_found=parts_found,
                kept=largest.name,
                deleted_names=deleted_names,
                kept_faces=len(largest.data.polygons),
            )

        return success(
            parts_found=parts_found,
            kept=base_name,
            deleted_names=[],
            kept_faces=len(obj.data.polygons) if obj.name in bpy.data.objects else 0,
        )

    # ------------------------------------------------------------------
    # 4. clean_mesh
    # ------------------------------------------------------------------
    @mcp.tool()
    def clean_mesh(
        object_name: str,
        remove_doubles: bool = True,
        merge_distance: float = 0.0001,
        remove_degenerate: bool = True,
        fill_holes: bool = False,
    ) -> dict:
        """Clean mesh geometry: merge nearby vertices, dissolve degenerate faces, and optionally fill holes."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        _set_active_and_select(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        report: dict = {}

        if remove_doubles:
            result = bpy.ops.mesh.remove_doubles(threshold=merge_distance)
            # Blender does not return the count directly; compute from mesh delta
            # We read the stat from the info area, but the simplest approach is
            # to count vertices before/after.
            report["merge_by_distance"] = {"threshold": merge_distance, "applied": True}

        if remove_degenerate:
            bpy.ops.mesh.dissolve_degenerate()
            report["dissolve_degenerate"] = True

        if fill_holes:
            bpy.ops.mesh.fill_holes(sides=4)
            report["fill_holes"] = True

        bpy.ops.object.mode_set(mode="OBJECT")

        mesh = obj.data
        report["final_vertices"] = len(mesh.vertices)
        report["final_faces"] = len(mesh.polygons)

        return success(**report)

    # ------------------------------------------------------------------
    # 5. boolean_operation
    # ------------------------------------------------------------------
    @mcp.tool()
    def boolean_operation(
        object_name: str,
        target_name: str,
        operation: str = "difference",
    ) -> dict:
        """Apply a boolean operation (union, difference, intersect) using target_name as the operand."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        target = bpy.data.objects.get(target_name)
        if target is None:
            return error(
                "ObjectNotFound", f"Target object '{target_name}' does not exist."
            )
        if target.type != "MESH":
            return error("NotAMesh", f"Target '{target_name}' is not a mesh.")

        op_map = {
            "union": "UNION",
            "difference": "DIFFERENCE",
            "intersect": "INTERSECT",
        }
        blender_op = op_map.get(operation.lower())
        if blender_op is None:
            return error(
                "InvalidOperation",
                f"Operation '{operation}' is not valid. Use: union, difference, intersect.",
            )

        _set_active_and_select(obj)
        mod = obj.modifiers.new(name="MCP_Boolean", type="BOOLEAN")
        mod.operation = blender_op
        mod.object = target

        bpy.ops.object.modifier_apply(modifier=mod.name)

        return success(result_faces=len(obj.data.polygons))

    # ------------------------------------------------------------------
    # 6. bisect_mesh
    # ------------------------------------------------------------------
    @mcp.tool()
    def bisect_mesh(
        object_name: str,
        plane_point: list[float] | None = None,
        plane_normal: list[float] | None = None,
        clear_inner: bool = False,
        clear_outer: bool = False,
    ) -> dict:
        """Bisect a mesh along a plane, optionally clearing inner or outer geometry."""
        if plane_point is None:
            plane_point = [0.0, 0.0, 0.0]
        if plane_normal is None:
            plane_normal = [0.0, 0.0, 1.0]

        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        _set_active_and_select(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        bpy.ops.mesh.bisect(
            plane_co=tuple(plane_point),
            plane_no=tuple(plane_normal),
            clear_inner=clear_inner,
            clear_outer=clear_outer,
        )

        bpy.ops.object.mode_set(mode="OBJECT")

        return success(faces=len(obj.data.polygons))

    # ------------------------------------------------------------------
    # 7. smooth_mesh
    # ------------------------------------------------------------------
    @mcp.tool()
    def smooth_mesh(
        object_name: str,
        iterations: int = 1,
        factor: float = 0.5,
        method: str = "simple",
    ) -> dict:
        """Smooth a mesh using a simple or Laplacian smooth modifier. Applied immediately."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        before_verts = len(obj.data.vertices)
        _set_active_and_select(obj)

        if method == "laplacian":
            mod = obj.modifiers.new(name="MCP_LaplacianSmooth", type="LAPLACIANSMOOTH")
            mod.iterations = iterations
            mod.lambda_factor = factor
        else:
            mod = obj.modifiers.new(name="MCP_Smooth", type="SMOOTH")
            mod.iterations = iterations
            mod.factor = factor

        bpy.ops.object.modifier_apply(modifier=mod.name)
        after_verts = len(obj.data.vertices)

        return success(
            before_vertices=before_verts,
            after_vertices=after_verts,
        )

    # ------------------------------------------------------------------
    # 8. create_vertex_group
    # ------------------------------------------------------------------
    @mcp.tool()
    def create_vertex_group(
        object_name: str,
        group_name: str,
        criteria: str = "normal_z_above",
        threshold: float = 0.85,
    ) -> dict:
        """Create a vertex group by selecting vertices matching a criteria (normal_z_above/below, height_above/below)."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        mesh = obj.data
        valid_criteria = {
            "normal_z_above",
            "normal_z_below",
            "height_above",
            "height_below",
        }
        if criteria not in valid_criteria:
            return error(
                "InvalidCriteria",
                f"Criteria '{criteria}' not valid. Use one of: {sorted(valid_criteria)}",
            )

        # Ensure face normals are up to date
        mesh.calc_normals_split()

        vg = obj.vertex_groups.get(group_name)
        if vg is None:
            vg = obj.vertex_groups.new(name=group_name)

        selected_verts: set[int] = set()

        if criteria.startswith("normal_z"):
            for poly in mesh.polygons:
                nz = poly.normal.z
                match = (criteria == "normal_z_above" and nz > threshold) or (
                    criteria == "normal_z_below" and nz < threshold
                )
                if match:
                    selected_verts.update(poly.vertices)
        else:
            # height-based
            for vert in mesh.vertices:
                # Use world-space Z
                world_z = (obj.matrix_world @ vert.co).z
                match = (criteria == "height_above" and world_z > threshold) or (
                    criteria == "height_below" and world_z < threshold
                )
                if match:
                    selected_verts.add(vert.index)

        if selected_verts:
            vg.add(list(selected_verts), 1.0, "REPLACE")

        return success(group_name=vg.name, vertex_count=len(selected_verts))

    # ------------------------------------------------------------------
    # 9. classify_surfaces
    # ------------------------------------------------------------------
    @mcp.tool()
    def classify_surfaces(
        object_name: str,
        road_threshold: float = 0.85,
        cliff_min: float = 0.2,
        vegetation_max: float = 0.2,
    ) -> dict:
        """Classify mesh faces into Road, Cliff, and Vegetation vertex groups based on face normal Z component."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        mesh = obj.data
        mesh.calc_normals_split()

        # Create or get vertex groups
        group_defs = {
            "Road_High_Res": {"verts": set(), "face_count": 0},
            "Cliff_High_Res": {"verts": set(), "face_count": 0},
            "Roadside_Vegetation": {"verts": set(), "face_count": 0},
        }

        for name in group_defs:
            if obj.vertex_groups.get(name) is None:
                obj.vertex_groups.new(name=name)

        for poly in mesh.polygons:
            nz = poly.normal.z
            if nz > road_threshold:
                key = "Road_High_Res"
            elif cliff_min <= nz <= road_threshold:
                key = "Cliff_High_Res"
            elif nz < vegetation_max:
                key = "Roadside_Vegetation"
            else:
                continue

            group_defs[key]["face_count"] += 1
            group_defs[key]["verts"].update(poly.vertices)

        # Assign vertices to groups
        for name, data in group_defs.items():
            vg = obj.vertex_groups[name]
            if data["verts"]:
                vg.add(list(data["verts"]), 1.0, "REPLACE")

        result = {}
        for name, data in group_defs.items():
            result[name] = {
                "vertex_count": len(data["verts"]),
                "face_count": data["face_count"],
            }

        return success(
            road=result["Road_High_Res"],
            cliff=result["Cliff_High_Res"],
            vegetation=result["Roadside_Vegetation"],
        )

    # ------------------------------------------------------------------
    # 10. remove_faces
    # ------------------------------------------------------------------
    @mcp.tool()
    def remove_faces(
        object_name: str,
        vertex_group: str = "",
        normal_threshold: float = 0.0,
        height_range: list[float] | None = None,
        force: bool = False,
    ) -> dict:
        """Remove faces matching criteria (vertex group, normal threshold, or height range). Respects tile transform protection."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        try:
            check_tile_transform(obj, force)
        except ValueError as exc:
            return error("TransformViolation", str(exc))

        mesh = obj.data
        before_faces = len(mesh.polygons)

        # Determine which faces to remove
        face_indices_to_remove: set[int] = set()

        if vertex_group:
            vg = obj.vertex_groups.get(vertex_group)
            if vg is None:
                return error(
                    "VertexGroupNotFound",
                    f"Vertex group '{vertex_group}' does not exist on '{object_name}'.",
                )
            vg_index = vg.index
            # Build set of vertices in this group
            group_verts: set[int] = set()
            for vert in mesh.vertices:
                for g in vert.groups:
                    if g.group == vg_index:
                        group_verts.add(vert.index)
                        break
            # Select faces where ALL vertices are in the group
            for poly in mesh.polygons:
                if all(vi in group_verts for vi in poly.vertices):
                    face_indices_to_remove.add(poly.index)

        if normal_threshold != 0.0:
            mesh.calc_normals_split()
            for poly in mesh.polygons:
                if poly.normal.z < normal_threshold:
                    face_indices_to_remove.add(poly.index)

        if height_range is not None and len(height_range) == 2:
            min_z, max_z = height_range
            for poly in mesh.polygons:
                centroid = obj.matrix_world @ poly.center
                if min_z <= centroid.z <= max_z:
                    face_indices_to_remove.add(poly.index)

        if not face_indices_to_remove:
            return success(removed=0, remaining=before_faces)

        # Enter edit mode, deselect all, select target faces, delete
        _set_active_and_select(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")

        # Switch to face select mode
        bpy.ops.mesh.select_mode(type="FACE")

        # Use bmesh to select specific faces
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()

        for fi in face_indices_to_remove:
            if fi < len(bm.faces):
                bm.faces[fi].select = True

        bmesh.update_edit_mesh(mesh)

        bpy.ops.mesh.delete(type="FACE")
        bpy.ops.object.mode_set(mode="OBJECT")

        after_faces = len(obj.data.polygons)

        return success(
            removed=before_faces - after_faces,
            remaining=after_faces,
        )

    # ------------------------------------------------------------------
    # 11. project_uv
    # ------------------------------------------------------------------
    @mcp.tool()
    def project_uv(
        object_name: str,
        direction: str = "top_down",
        uv_layer_name: str = "UVMap",
    ) -> dict:
        """Project UVs onto a mesh. Supports top_down (project from view) and cube projection methods."""
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        mesh = obj.data

        # Create UV layer if needed
        if uv_layer_name not in mesh.uv_layers:
            mesh.uv_layers.new(name=uv_layer_name)
        mesh.uv_layers.active = mesh.uv_layers[uv_layer_name]

        _set_active_and_select(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        if direction == "cube":
            bpy.ops.uv.cube_project()
        else:
            # top_down: use smart_project as a reliable fallback that doesn't
            # require a specific 3D viewport camera orientation
            bpy.ops.uv.smart_project(angle_limit=1.15192)  # ~66 degrees

        bpy.ops.object.mode_set(mode="OBJECT")

        return success(
            uv_layer_name=uv_layer_name,
            face_count=len(mesh.polygons),
        )

    # ------------------------------------------------------------------
    # 12. compute_envelope
    # ------------------------------------------------------------------
    @mcp.tool()
    def compute_envelope(
        object_name: str,
        grid_res: float = 3.0,
        height_threshold: float = 4.0,
    ) -> dict:
        """Remove canopy/overhead geometry by raycasting a ground height map and deleting faces above the ground envelope.

        Algorithm: build a 2D grid, cast rays downward to find the lowest
        surface in each column, then delete faces whose centroids are more
        than height_threshold above the local ground height.
        """
        _ensure_object_mode()
        obj, err = _get_mesh_object(object_name)
        if err:
            return err

        from mathutils import Vector

        mesh = obj.data
        bb = bounding_box(obj)
        min_x, min_y, min_z = bb["min"]
        max_x, max_y, max_z = bb["max"]

        # Build grid
        nx = max(1, int(math.ceil((max_x - min_x) / grid_res)))
        ny = max(1, int(math.ceil((max_y - min_y) / grid_res)))
        grid_cells_total = nx * ny

        # Inverse world matrix for converting world coords to local space
        mat_inv = obj.matrix_world.inverted()

        ray_origin_z = max_z + 1.0
        ray_dir_world = Vector((0.0, 0.0, -1.0))

        # Transform ray direction to local space (direction only, no translation)
        ray_dir_local = (mat_inv.to_3x3() @ ray_dir_world).normalized()

        ground_heights: dict[tuple[int, int], float] = {}
        grid_cells_with_hits = 0

        for ix in range(nx):
            cx = min_x + (ix + 0.5) * grid_res
            for iy in range(ny):
                cy = min_y + (iy + 0.5) * grid_res

                # Cast rays downward, finding the LOWEST hit
                origin_world = Vector((cx, cy, ray_origin_z))
                origin_local = mat_inv @ origin_world

                lowest_z = None
                current_origin = origin_local.copy()
                max_casts = 50  # safety limit

                for _ in range(max_casts):
                    hit, loc, _normal, _fi = obj.ray_cast(current_origin, ray_dir_local)
                    if not hit:
                        break

                    # Convert hit location to world space for Z comparison
                    hit_world = obj.matrix_world @ loc
                    if lowest_z is None or hit_world.z < lowest_z:
                        lowest_z = hit_world.z

                    # Move origin just below this hit in local space and cast again
                    # Nudge downward by a small amount in world space
                    nudge_world = Vector((cx, cy, hit_world.z - 0.01))
                    current_origin = mat_inv @ nudge_world

                    # If we've gone below the bounding box floor, stop
                    if hit_world.z - 0.01 < min_z:
                        break

                if lowest_z is not None:
                    ground_heights[(ix, iy)] = lowest_z
                    grid_cells_with_hits += 1

        # Safety check: if too few cells have hits, abort
        if grid_cells_total > 0 and grid_cells_with_hits / grid_cells_total < 0.5:
            return error(
                "InsufficientCoverage",
                f"Only {grid_cells_with_hits}/{grid_cells_total} grid cells had ray hits. "
                f"Aborting to avoid incorrect deletion.",
                grid_cells_total=grid_cells_total,
                grid_cells_with_hits=grid_cells_with_hits,
            )

        # Identify faces to delete
        faces_to_remove: set[int] = set()
        mesh.calc_normals_split()

        for poly in mesh.polygons:
            centroid_world = obj.matrix_world @ poly.center
            cz = centroid_world.z

            # Find nearest grid cell
            ix = int((centroid_world.x - min_x) / grid_res)
            iy = int((centroid_world.y - min_y) / grid_res)
            ix = max(0, min(ix, nx - 1))
            iy = max(0, min(iy, ny - 1))

            ground_z = ground_heights.get((ix, iy))
            if ground_z is None:
                # No hit in this column -- be conservative, skip
                continue

            # Never delete faces below or at ground level
            if cz <= ground_z:
                continue

            if cz > ground_z + height_threshold:
                faces_to_remove.add(poly.index)

        before_faces = len(mesh.polygons)

        if not faces_to_remove:
            return success(
                faces_removed=0,
                faces_remaining=before_faces,
                grid_cells_total=grid_cells_total,
                grid_cells_with_hits=grid_cells_with_hits,
            )

        # Delete marked faces
        _set_active_and_select(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.mesh.select_mode(type="FACE")

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()

        for fi in faces_to_remove:
            if fi < len(bm.faces):
                bm.faces[fi].select = True

        bmesh.update_edit_mesh(mesh)
        bpy.ops.mesh.delete(type="FACE")
        bpy.ops.object.mode_set(mode="OBJECT")

        after_faces = len(obj.data.polygons)

        # Separate loose parts and keep largest
        base_name = obj.name
        _set_active_and_select(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        try:
            bpy.ops.mesh.separate(type="LOOSE")
        except RuntimeError:
            pass  # No loose parts to separate

        bpy.ops.object.mode_set(mode="OBJECT")

        # Find all parts
        parts = [
            o
            for o in bpy.data.objects
            if o.type == "MESH"
            and (o.name == base_name or o.name.startswith(base_name + "."))
        ]

        if len(parts) > 1:
            largest = max(parts, key=lambda o: len(o.data.polygons))
            for part in parts:
                if part is not largest:
                    bpy.data.objects.remove(part, do_unlink=True)
            after_faces = len(largest.data.polygons)

        return success(
            faces_removed=before_faces - after_faces,
            faces_remaining=after_faces,
            grid_cells_total=grid_cells_total,
            grid_cells_with_hits=grid_cells_with_hits,
        )
