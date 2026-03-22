# blender-mcp — Project Context for Claude Code

## Overview

MCP server for Blender 5.1+. The server runs **embedded inside Blender's Python process** using FastMCP on Streamable HTTP (port 8800). Claude Code communicates with it via a stdio proxy that bridges to the HTTP server.

This is part of a broader ecosystem of MCP servers: metashape-mcp (photogrammetry), resolve-mcp (video editing), and others.

## Architecture

```
Claude Code
    |
    | stdio
    v
blender_mcp.proxy  (runs via: uv run blender-mcp)
    |
    | HTTP (localhost:8800)
    v
FastMCP server  (embedded in Blender's Python process)
    |
    | bpy API calls (main thread only)
    v
Blender 5.1+
```

Key design decisions:
- **Embedded server**: FastMCP runs in a background thread inside Blender using `bpy.app.timers`. Tool handlers push work onto a queue; a timer fires on the main thread to drain the queue and execute bpy calls.
- **Stdio proxy**: The `blender_mcp.proxy` module is the entry point registered with Claude Code. It speaks stdio MCP and forwards to the HTTP server.
- **Module-per-domain tool registration**: Tools are split across domain modules (scene, mesh, materials, io, terrain, etc.). Each module exports a `register(mcp)` function. This keeps files focused and avoids a monolithic server module.

## Module Registration Pattern

Each tool module in `src/blender_mcp/tools/` exports a `register` function:

```python
# tools/scene.py
def register(mcp):
    @mcp.tool()
    def get_scene_info() -> dict:
        ...
```

The `tools/__init__.py` collects and calls all registrations:

```python
# tools/__init__.py
from . import scene, mesh, materials, io, terrain

def register_all(mcp):
    scene.register(mcp)
    mesh.register(mcp)
    materials.register(mcp)
    io.register(mcp)
    terrain.register(mcp)
```

Same pattern applies to `resources/`.

## Agent Rules

These rules apply to ALL agents and Claude Code sessions working in this project:

1. **NEVER batch tool calls** — call tools individually and await results. Blender's main thread queue processes one item at a time; batching causes race conditions.
2. **NEVER alter object-level transforms on `Tile_*` objects** — terrain tile transforms are set by the photogrammetry pipeline (metashape-mcp) and must not be modified. Only mesh data operations are permitted on tiles.
3. **ALWAYS save after major operations** — call `save_blend_file` after any destructive or batch operation. Blender does not auto-save.
4. **All mesh operations run on the main thread** — long mesh operations will block Blender's UI. This is expected; do not attempt to thread bpy calls.

## Running

### Start the embedded server (inside Blender's Python console)
```python
from blender_mcp.server import start_background
start_background()
```

Or enable the addon from Blender Preferences > Add-ons and click "Start Server" in the N-panel sidebar.

### Start the stdio proxy (for Claude Code)
```bash
uv run blender-mcp
```

The proxy expects the Blender server to already be running on localhost:8800.

## Development

**Project location:** `/Volumes/4TB G-SSD/ASC_4x4/repos/blender-mcp/`

**Symlink the addon into Blender's addons directory** so edits take effect without reinstalling:
```bash
# Blender 5.1 addon path (adjust version as needed)
ln -s /Volumes/4TB\ G-SSD/ASC_4x4/repos/blender-mcp/src/blender_mcp \
      ~/Library/Application\ Support/Blender/5.1/scripts/addons/blender_mcp
```

**FastMCP must be installed in Blender's bundled Python**, not just the project venv:
```bash
# Find Blender's Python
/Applications/Blender.app/Contents/Resources/5.1/python/bin/python3 -m pip install fastmcp
```

**Register with Claude Code** (user scope so it's available everywhere):
```bash
claude mcp add --scope user blender-mcp -- uv run --directory /Volumes/4TB\ G-SSD/ASC_4x4/repos/blender-mcp blender-mcp
```

## Dependencies

- `fastmcp>=2.0.0` — FastMCP framework (installed both in project venv and Blender's Python)
- `mcp[cli]>=1.2.0` — MCP SDK + CLI
- `bpy` — provided by Blender; NOT installed in the project venv

## Integration with metashape-mcp

blender-mcp and metashape-mcp share a terrain pipeline convention:

- **Tile naming**: `Tile_X-Y` (e.g., `Tile_0-0`, `Tile_3-7`) — both MCPs use this naming scheme
- **Workflow**: Metashape exports OBJ tiles → Blender imports and processes them
- **Transform freeze**: Tile object transforms are set by Metashape's coordinate system; blender-mcp tools must not overwrite them

When working on terrain tools, check metashape-mcp's `CLAUDE.md` for the shared conventions.
