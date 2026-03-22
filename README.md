# blender-mcp

MCP server for Blender 5.1+ — embedded FastMCP server with tools for scene management, mesh operations, import/export, and photogrammetry terrain processing.

## Installation

### 1. Install FastMCP into Blender's Python

```bash
/Applications/Blender.app/Contents/Resources/5.1/python/bin/python3 -m pip install fastmcp
```

### 2. Symlink the addon into Blender's addons directory

```bash
ln -s /Volumes/4TB\ G-SSD/ASC_4x4/repos/blender-mcp/src/blender_mcp \
      ~/Library/Application\ Support/Blender/5.1/scripts/addons/blender_mcp
```

Then enable the addon in Blender: Preferences > Add-ons > search "blender-mcp" > enable.

### 3. Register with Claude Code

```bash
claude mcp add --scope user blender-mcp -- uv run --directory /Volumes/4TB\ G-SSD/ASC_4x4/repos/blender-mcp blender-mcp
```

## Usage

1. Open Blender and enable the blender-mcp addon (Preferences > Add-ons).
2. In the 3D Viewport, open the N-panel (press N) and find the "MCP" tab.
3. Click "Start Server" to start the embedded FastMCP server on port 8800.
4. Claude Code will connect automatically via the registered stdio proxy.

## Phase Roadmap

### Phase 1: Foundation + Terrain
Core scene management, object operations, mesh editing primitives, OBJ/FBX import/export, and photogrammetry terrain tile processing tools. Integration with metashape-mcp pipeline.

### Phase 2: Game-Ready Assets
UV unwrapping, LOD generation, material baking, texture atlas tools, and asset packaging for game engine export.

### Phase 3: Racing Environment
Road surface tools, track boundary helpers, environment dressing workflows, and batch export utilities optimized for the Real Sim Roads pipeline.
