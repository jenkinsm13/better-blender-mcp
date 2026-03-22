"""Tile naming convention helpers for Tile_X-Y pattern."""

from __future__ import annotations
import re

_TILE_RE = re.compile(r"^Tile_(\d+)-(\d+)$")


def parse_tile_name(name: str) -> tuple[int, int] | None:
    """Parse 'Tile_X-Y' -> (x, y) or None if not a tile."""
    m = _TILE_RE.match(name)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def is_tile(name: str) -> bool:
    """Check if name matches Tile_X-Y pattern."""
    return _TILE_RE.match(name) is not None


def tile_grid_summary(names: list[str]) -> dict:
    """Analyze a list of object names for tile grid coverage."""
    tiles: list[tuple[int, int]] = []
    non_tiles: list[str] = []

    for name in names:
        parsed = parse_tile_name(name)
        if parsed:
            tiles.append(parsed)
        else:
            non_tiles.append(name)

    if not tiles:
        return {
            "tile_count": 0,
            "grid_min": None,
            "grid_max": None,
            "gaps": [],
            "non_tile_objects": sorted(non_tiles),
        }

    xs = [t[0] for t in tiles]
    ys = [t[1] for t in tiles]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    tile_set = set(tiles)
    gaps = []
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            if (x, y) not in tile_set:
                gaps.append(f"Tile_{x}-{y}")

    return {
        "tile_count": len(tiles),
        "grid_min": [min_x, min_y],
        "grid_max": [max_x, max_y],
        "gaps": sorted(gaps),
        "non_tile_objects": sorted(non_tiles),
    }
