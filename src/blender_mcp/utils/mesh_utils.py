"""Shared mesh analysis helpers.

Functions here require bpy and are used by multiple tool modules.
Not unit-testable outside Blender -- tested via integration tests.
"""

from __future__ import annotations


def bounding_box(obj) -> dict:
    """Get world-space bounding box for a mesh object."""
    from mathutils import Vector

    coords = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    min_v = [min(xs), min(ys), min(zs)]
    max_v = [max(xs), max(ys), max(zs)]
    return {
        "min": min_v,
        "max": max_v,
        "center": [(a + b) / 2 for a, b in zip(min_v, max_v)],
        "dimensions": [b - a for a, b in zip(min_v, max_v)],
    }


def is_identity_transform(obj) -> bool:
    """Check if object has identity transform (loc=0, rot=0, scale=1)."""
    loc = obj.location
    rot = obj.rotation_euler
    scale = obj.scale
    eps = 1e-6
    return (
        all(abs(v) < eps for v in loc)
        and all(abs(v) < eps for v in rot)
        and all(abs(v - 1.0) < eps for v in scale)
    )


def check_tile_transform(obj, force: bool = False) -> None:
    """Raise ValueError if obj is a Tile_* with non-identity transform.

    Args:
        obj: bpy.types.Object to check.
        force: If True, skip the check.

    Raises:
        ValueError: With TransformViolation message.
    """
    from blender_mcp.utils.naming import is_tile

    if not force and is_tile(obj.name) and not is_identity_transform(obj):
        raise ValueError(
            f"TransformViolation: {obj.name} has non-identity transform. "
            f"Pass force=True to override."
        )
