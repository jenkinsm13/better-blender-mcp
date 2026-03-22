from blender_mcp.utils.naming import parse_tile_name, is_tile, tile_grid_summary


def test_parse_valid_tile():
    assert parse_tile_name("Tile_3-7") == (3, 7)


def test_parse_invalid_tile():
    assert parse_tile_name("Cube") is None


def test_is_tile():
    assert is_tile("Tile_0-0") is True
    assert is_tile("Tile_12-34") is True
    assert is_tile("Camera") is False
    assert is_tile("Tile_abc") is False


def test_tile_grid_summary():
    names = ["Tile_0-0", "Tile_0-1", "Tile_1-0", "Tile_1-1", "Camera"]
    summary = tile_grid_summary(names)
    assert summary["tile_count"] == 4
    assert summary["grid_min"] == [0, 0]
    assert summary["grid_max"] == [1, 1]
    assert summary["non_tile_objects"] == ["Camera"]


def test_tile_grid_detects_gaps():
    names = ["Tile_0-0", "Tile_0-2", "Tile_1-0", "Tile_1-2"]
    summary = tile_grid_summary(names)
    assert summary["gaps"] == ["Tile_0-1", "Tile_1-1"]
