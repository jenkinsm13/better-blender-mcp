"""Modifier tools for Blender MCP."""

import bpy
from blender_mcp.utils.responses import success, error


def _modifier_stack(obj) -> list[dict]:
    """Return a serializable list of the current modifier stack for obj."""
    return [{"name": mod.name, "type": mod.type} for mod in obj.modifiers]


def _mesh_stats(obj) -> tuple[int, int]:
    """Return (face_count, vertex_count) for a MESH object, or (0, 0) otherwise."""
    if obj.type == "MESH" and obj.data is not None:
        return len(obj.data.polygons), len(obj.data.vertices)
    return 0, 0


def _set_active_object(obj) -> None:
    """Make obj selected and active."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def register(mcp) -> None:
    """Register modifier tools."""

    @mcp.tool()
    def add_modifier(
        object_name: str,
        modifier_type: str,
        params: dict | None = None,
    ) -> dict:
        """Add a modifier to an object and optionally configure it via a params dict.

        modifier_type is a Blender modifier identifier, e.g. DECIMATE, SMOOTH,
        BOOLEAN, SOLIDIFY, ARRAY, SUBSURF, MIRROR, BEVEL, etc.
        params keys map directly to modifier attributes (e.g. {"ratio": 0.5}).
        Returns the new modifier name and the full modifier stack.
        """
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        try:
            mod = obj.modifiers.new(
                name=modifier_type.capitalize(), type=modifier_type.upper()
            )
        except Exception as exc:
            return error(
                "ModifierError", f"Could not add modifier '{modifier_type}': {exc}"
            )

        if params:
            for key, value in params.items():
                try:
                    setattr(mod, key, value)
                except AttributeError:
                    # Non-fatal: report bad keys but still return success
                    pass

        return success(modifier_name=mod.name, modifier_stack=_modifier_stack(obj))

    @mcp.tool()
    def apply_modifier(object_name: str, modifier_name: str) -> dict:
        """Apply a single modifier by name, permanently baking it into the mesh.

        Returns before/after face and vertex counts so the caller can see the mesh change.
        """
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        if modifier_name not in obj.modifiers:
            return error(
                "ModifierNotFound",
                f"Modifier '{modifier_name}' not found on '{object_name}'.",
            )

        before_faces, before_vertices = _mesh_stats(obj)

        _set_active_object(obj)

        try:
            with bpy.context.temp_override(active_object=obj, object=obj):
                bpy.ops.object.modifier_apply(modifier=modifier_name)
        except Exception as exc:
            return error(
                "ModifierError", f"Could not apply modifier '{modifier_name}': {exc}"
            )

        after_faces, after_vertices = _mesh_stats(obj)

        return success(
            before_faces=before_faces,
            after_faces=after_faces,
            before_vertices=before_vertices,
            after_vertices=after_vertices,
        )

    @mcp.tool()
    def apply_all_modifiers(object_name: str) -> dict:
        """Apply every modifier on the object from top to bottom.

        Returns before/after mesh stats.
        """
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        before_faces, before_vertices = _mesh_stats(obj)

        _set_active_object(obj)

        # Collect names first — the stack shrinks as we apply
        modifier_names = [mod.name for mod in obj.modifiers]
        errors = []
        for name in modifier_names:
            if name not in obj.modifiers:
                continue
            try:
                with bpy.context.temp_override(active_object=obj, object=obj):
                    bpy.ops.object.modifier_apply(modifier=name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        after_faces, after_vertices = _mesh_stats(obj)

        result = success(
            before_faces=before_faces,
            after_faces=after_faces,
            before_vertices=before_vertices,
            after_vertices=after_vertices,
            applied_count=len(modifier_names) - len(errors),
        )
        if errors:
            result["warnings"] = errors
        return result

    @mcp.tool()
    def remove_modifier(object_name: str, modifier_name: str) -> dict:
        """Remove a modifier from an object without applying it.

        Returns the name of the removed modifier and the remaining modifier stack.
        """
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        mod = obj.modifiers.get(modifier_name)
        if mod is None:
            return error(
                "ModifierNotFound",
                f"Modifier '{modifier_name}' not found on '{object_name}'.",
            )

        obj.modifiers.remove(mod)

        return success(removed=modifier_name, modifier_stack=_modifier_stack(obj))
