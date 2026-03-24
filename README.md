# better-blender-mcp

MCP server for Blender 5.1+ with 47 tools for scene management, mesh operations, viewport capture, import/export, and photogrammetry terrain processing. Replaces the basic community Blender MCP with proper tool coverage.

## Requirements

- Blender 5.1+
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Claude Code

## Installation

### 1. Install the Claude Code plugin

```bash
# Add the marketplace (one-time)
claude plugin marketplace add https://github.com/jenkinsm13/claude-plugins

# Install the plugin
claude plugin install better-blender-mcp
```

Or register manually:
```bash
claude mcp add --scope user blender-mcp -- uv run --directory /path/to/better-blender-mcp blender-mcp
```

### 2. Install FastMCP into Blender's Python

Blender ships its own Python — FastMCP must be installed there:

```bash
# macOS
/Applications/Blender.app/Contents/Resources/5.1/python/bin/python3 -m pip install fastmcp

# Linux
/path/to/blender/5.1/python/bin/python3 -m pip install fastmcp

# Windows
"C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" -m pip install fastmcp
```

### 3. Install the Blender addon

Symlink the addon source into Blender's addons directory:

```bash
# macOS
ln -s /path/to/better-blender-mcp/src/blender_mcp \
      ~/Library/Application\ Support/Blender/5.1/scripts/addons/blender_mcp

# Linux
ln -s /path/to/better-blender-mcp/src/blender_mcp \
      ~/.config/blender/5.1/scripts/addons/blender_mcp

# Windows (run as admin)
mklink /D "%APPDATA%\Blender Foundation\Blender\5.1\scripts\addons\blender_mcp" \
       C:\path\to\better-blender-mcp\src\blender_mcp
```

Then enable in Blender: **Preferences > Add-ons > search "Blender MCP" > enable**.

## Usage

1. Open Blender
2. In the 3D Viewport sidebar (press **N**), find the **BlenderMCP** tab
3. Click **Start MCP Server** (runs on port 8800)
4. Start Claude Code — it connects automatically via the stdio proxy

## Architecture

```
Claude Code  ──stdio──>  proxy.py  ──HTTP──>  FastMCP server (inside Blender)
                                                    │
                                              ExecutionQueue
                                                    │
                                              bpy.app.timers (main thread)
```

The MCP server runs embedded in Blender's process with direct `bpy` access. A stdio-to-HTTP proxy bridges Claude Code to the server. All tool calls are routed through an `ExecutionQueue` to Blender's main thread via `bpy.app.timers`, where `bpy.ops` and full context are available.

## Tools (47)

| Category | Tools |
|----------|-------|
| **Scene** | `get_scene_info`, `list_objects`, `get_object_info`, `select_objects`, `delete_objects`, `create_collection`, `move_to_collection`, `set_active_object`, `execute_python` |
| **Mesh** | `get_mesh_stats`, `clean_mesh`, `decimate_mesh`, `smooth_mesh`, `separate_loose`, `boolean_operation`, `bisect_mesh`, `remove_faces`, `project_uv`, `create_vertex_group`, `classify_surfaces`, `compute_envelope` |
| **Viewport** | `capture_viewport`, `capture_viewport_4pack`, `set_viewport_shading`, `frame_objects`, `set_viewport_overlay` |
| **Import/Export** | `import_obj`, `import_fbx`, `import_ply`, `export_obj`, `export_fbx`, `export_ply`, `batch_import`, `batch_export`, `export_kn5` (stub), `export_kpm` (stub) |
| **Modifiers** | `add_modifier`, `apply_modifier`, `apply_all_modifiers`, `remove_modifier` |
| **Transforms** | `get_transforms`, `apply_transforms`, `set_origin`, `align_objects` |
| **Project** | `open_file`, `save_file`, `get_project_state` |

## Viewport Capture

**`capture_viewport`** — Screenshot the active 3D viewport to PNG.

**`capture_viewport_4pack`** — Captures Top, Front, Right, and Perspective views, stitched into a 2x2 grid. Great for reviewing models from all angles in a single image.

## Tile Naming Convention

Objects named `Tile_X-Y` (e.g., `Tile_0-0`, `Tile_3-2`) are treated as photogrammetry terrain tiles. Transform modifications on tile objects are blocked unless `force=True` to prevent accidental misalignment.

## License

MIT
