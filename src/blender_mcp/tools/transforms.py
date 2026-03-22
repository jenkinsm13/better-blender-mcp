"""Transform tools for Blender MCP."""

import bpy
from blender_mcp.utils.responses import success, error
from blender_mcp.utils.mesh_utils import check_tile_transform

_VALID_ORIGIN_TYPES = {
    "GEOMETRY_ORIGIN",
    "ORIGIN_GEOMETRY",
    "ORIGIN_CURSOR",
    "ORIGIN_CENTER_OF_VOLUME",
    "ORIGIN_CENTER_OF_MASS",
}

_VALID_AXES = {"X", "Y", "Z"}


def _obj_transform_dict(obj) -> dict:
    """Serialize the location, rotation_euler, and scale of an object."""
    return {
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
    }


def register(mcp) -> None:
    """Register transform tools."""

    @mcp.tool()
    def get_transforms(object_names: list[str] | None = None) -> dict:
        """Return location, rotation_euler, and scale for the named objects.

        If object_names is None or empty, all scene objects are returned.
        """
        if object_names:
            transforms = {}
            for name in object_names:
                obj = bpy.data.objects.get(name)
                if obj is None:
                    return error("ObjectNotFound", f"Object '{name}' does not exist.")
                transforms[name] = _obj_transform_dict(obj)
        else:
            transforms = {
                obj.name: _obj_transform_dict(obj) for obj in bpy.context.scene.objects
            }

        return success(transforms=transforms)

    @mcp.tool()
    def apply_transforms(
        object_name: str,
        location: bool = True,
        rotation: bool = True,
        scale: bool = True,
        force: bool = False,
    ) -> dict:
        """Bake the current location/rotation/scale into the mesh data.

        For Tile_* objects, a non-identity transform is blocked unless force=True.
        """
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        try:
            check_tile_transform(obj, force)
        except ValueError as exc:
            return error("TransformViolation", str(exc))

        # Select and activate the target object
        for o in bpy.context.scene.objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        try:
            with bpy.context.temp_override(active_object=obj, object=obj):
                bpy.ops.object.transform_apply(
                    location=location,
                    rotation=rotation,
                    scale=scale,
                )
        except Exception as exc:
            return error("TransformError", f"Could not apply transforms: {exc}")

        return success(applied=True)

    @mcp.tool()
    def set_origin(
        object_name: str,
        origin_type: str = "GEOMETRY_ORIGIN",
        force: bool = False,
    ) -> dict:
        """Move the object's origin point.

        origin_type must be one of:
          GEOMETRY_ORIGIN, ORIGIN_GEOMETRY, ORIGIN_CURSOR,
          ORIGIN_CENTER_OF_VOLUME, ORIGIN_CENTER_OF_MASS.

        For Tile_* objects the tile-protection check runs unless force=True.
        Returns the new object location (which moves when the origin moves).
        """
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return error("ObjectNotFound", f"Object '{object_name}' does not exist.")

        origin_type = origin_type.upper()
        if origin_type not in _VALID_ORIGIN_TYPES:
            return error(
                "InvalidArgument",
                f"origin_type must be one of {sorted(_VALID_ORIGIN_TYPES)}, "
                f"got '{origin_type}'.",
            )

        try:
            check_tile_transform(obj, force)
        except ValueError as exc:
            return error("TransformViolation", str(exc))

        for o in bpy.context.scene.objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        try:
            with bpy.context.temp_override(active_object=obj, object=obj):
                bpy.ops.object.origin_set(type=origin_type)
        except Exception as exc:
            return error("TransformError", f"Could not set origin: {exc}")

        return success(origin=list(obj.location))

    @mcp.tool()
    def align_objects(
        object_names: list[str],
        axis: str = "X",
        align_type: str = "CENTER",
        force: bool = False,
    ) -> dict:
        """Align a set of objects along an axis relative to the first object in the list.

        axis: X, Y, or Z.
        align_type: CENTER, POSITIVE, NEGATIVE, or a value accepted by
                    bpy.ops.object.align (align_mode parameter).
        The first name in object_names becomes the active (reference) object.
        For Tile_* objects the tile-protection check runs on each object unless force=True.
        Returns the aligned count and a dict of final positions.
        """
        if not object_names:
            return error("InvalidArgument", "object_names must not be empty.")

        axis = axis.upper()
        if axis not in _VALID_AXES:
            return error(
                "InvalidArgument",
                f"axis must be one of {sorted(_VALID_AXES)}, got '{axis}'.",
            )

        objects = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj is None:
                return error("ObjectNotFound", f"Object '{name}' does not exist.")
            try:
                check_tile_transform(obj, force)
            except ValueError as exc:
                return error("TransformViolation", str(exc))
            objects.append(obj)

        # Deselect all, then select targets
        for o in bpy.context.scene.objects:
            o.select_set(False)
        for obj in objects:
            obj.select_set(True)

        # First object is the active reference
        bpy.context.view_layer.objects.active = objects[0]

        try:
            with bpy.context.temp_override(
                active_object=objects[0],
                selected_objects=objects,
                selected_editable_objects=objects,
            ):
                bpy.ops.object.align(
                    align_axis={axis},
                    relative_to="ACTIVE",
                    align_mode=align_type,
                )
        except Exception as exc:
            return error("TransformError", f"Could not align objects: {exc}")

        positions = {obj.name: list(obj.location) for obj in objects}
        return success(aligned_count=len(objects), positions=positions)
