---
name: game-ready-export
description: Batch FBX export with game-engine golden rules, pre-export checklist, and post-export verification.
---

# Game-Ready Export

## Overview

Export processed terrain tiles as FBX files ready for game engine import. Enforces strict conventions to prevent common import issues.

## FBX Golden Rules

These are NON-NEGOTIABLE for every export:

1. `apply_scale_options = "FBX_SCALE_NONE"` - photogrammetry tiles are already in real-world meters
2. `axis_forward = "-Z"`, `axis_up = "Y"` - standard Blender-to-game-engine convention
3. Identity transforms on ALL objects - Location=(0,0,0), Rotation=(0,0,0), Scale=(1,1,1)
4. `use_tspace = True` - tangent space for normal maps
5. `mesh_smooth_type = "OFF"` - no auto-smooth on photogrammetry meshes

## Pre-Export Checklist

Run these checks before exporting:

- [ ] All Tile_* objects have identity transforms (`get_transforms`)
- [ ] All meshes are triangulated (no n-gons)
- [ ] Vertex groups present (Road_High_Res, Cliff_High_Res, Roadside_Vegetation)
- [ ] UV layer exists on all tiles
- [ ] File saved (`save_file`)

If any check fails, fix the issue before proceeding.

## Export Workflow

### Step 1: Pre-Flight
1. `get_transforms` on all tile objects - verify identity
2. `get_mesh_stats` on each tile - verify faces > 0, has UV
3. `save_file`

### Step 2: Batch Export
1. `batch_export(directory="/path/to/output", format="fbx")`
2. Review per-tile results

### Step 3: Post-Export Verification
1. Check file sizes are reasonable (100MB-500MB per tile for high-res)
2. Check all expected tiles were exported (compare against tile grid)
3. Report total export size

## Output Structure

```
output_directory/
├── Tile_0-0.fbx
├── Tile_0-1.fbx
├── Tile_1-0.fbx
├── Tile_1-1.fbx
└── ...
```

## Common Pitfalls

- **FBX_SCALE_ALL instead of NONE**: Tiles will be 100x wrong size in engine. ALWAYS use NONE.
- **Wrong axis convention**: Tiles will appear rotated 90 degrees. Use -Z forward, Y up.
- **Non-identity transforms**: Engine may double-apply the transform, causing tiles to fly apart.
- **Missing UVs**: Texture won't map correctly. Run project_uv before export.
