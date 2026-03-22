---
name: metashape-round-trip
description: Export cleaned meshes from Blender to Metashape for re-texturing, then import the textured result back.
---

# Metashape Round-Trip

## Overview

After cleaning terrain meshes in Blender, they can be sent back to Metashape for photo-texturing. This produces high-quality textures from the original photographs, applied to the cleaned geometry.

## Prerequisites

- Cleaned meshes in Blender (terrain-cleanup-pipeline complete)
- Metashape project open with the same chunk that produced the original meshes
- metashape-mcp server running

## Workflow

### Step 1: Export from Blender

For each tile to re-texture:
1. `export_obj(path="/path/to/exchange/Tile_X-Y.obj", object_name="Tile_X-Y")`
2. OBJ format preserves geometry and UVs
3. Axis convention: forward=-Z, up=Y (matches Metashape expectations)

### Step 2: Import into Metashape

Using metashape-mcp tools:
1. `import_model(path="/path/to/exchange/Tile_X-Y.obj", format="obj")`
2. Verify model imported correctly

### Step 3: Build Texture in Metashape

Using metashape-mcp tools:
1. `build_uv(mapping_mode="generic", texture_size=8192)`
2. `build_texture(blending_mode="mosaic", texture_size=8192, ghosting_filter=True)`
3. Mosaic blending produces the sharpest results for road surfaces

### Step 4: Export Textured Model from Metashape

Using metashape-mcp tools:
1. `export_model(path="/path/to/exchange/Tile_X-Y_textured.fbx", format="fbx", save_texture=True)`

### Step 5: Import Textured Model into Blender

1. `import_fbx(path="/path/to/exchange/Tile_X-Y_textured.fbx")`
2. Verify texture is applied
3. Verify geometry matches (face count should be same or very close)

## Coordinate System Notes

| Stage | Forward | Up | Units |
|-------|---------|-----|-------|
| Blender export (OBJ) | -Z | Y | meters |
| Metashape import | auto-detected | auto-detected | meters |
| Metashape export (FBX) | auto | auto | meters |
| Blender import (FBX) | -Z | Y | meters |

## Common Pitfalls

- **Scale mismatch**: If the re-imported model is 100x too large or small, the CRS units in Metashape may be degrees instead of meters. Check Metashape chunk CRS.
- **Texture not appearing**: Blender may not auto-assign the texture to a material. Check the material's image texture node.
- **UV overwrite**: Metashape's build_uv will create new UVs. The top-down projection from Phase 5 of cleanup will be replaced.
