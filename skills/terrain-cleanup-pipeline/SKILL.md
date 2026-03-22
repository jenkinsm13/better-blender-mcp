---
name: terrain-cleanup-pipeline
description: Full 6-phase terrain cleanup pipeline for photogrammetry tiles - assessment, cleanup, envelope, classification, UV, optimization.
---

# Terrain Cleanup Pipeline

## Overview

Processes raw photogrammetry terrain tiles from Metashape into clean, classified, UV-mapped meshes ready for game engine export. This is the core workflow for Real Sim Roads.

## Golden Rules

1. **NEVER remove upward-facing faces** (normal.z >= 0) - these ARE the terrain
2. **NEVER alter object-level transforms** on Tile_* objects
3. **ALWAYS save after every phase** - Blender crashes happen
4. **Process max 10 tiles per tool call** to avoid timeouts
5. **Verify results after each phase** before proceeding

## Phase 1: Assessment

**Tool:** `classify_surfaces(object_name)`

For each tile:
1. Call `classify_surfaces` with default thresholds (road > 0.85, cliff 0.2-0.85, vegetation < 0.2)
2. Calculate canopy percentage: vegetation_faces / total_faces
3. Categorize:
   - < 2% canopy: **SKIP** (clean enough)
   - 2-5% canopy: **MARGINAL** (basic cleanup only)
   - 5-15% canopy: **MODERATE** (basic + targeted envelope)
   - > 15% canopy: **HEAVY** (full envelope, may need manual review)

## Phase 2: Basic Cleanup

**Tools:** `separate_loose`, `remove_faces`

For MARGINAL, MODERATE, and HEAVY tiles:
1. `separate_loose(object_name, keep_largest=True)` - remove disconnected fragments
2. `remove_faces(object_name, normal_threshold=-0.2)` - remove downward-facing + high faces
3. `separate_loose(object_name, keep_largest=True)` - clean up post-cut fragments
4. Delete tiny resulting objects (< 500 faces)
5. `save_file()`

## Phase 3: Targeted Envelope

**Tool:** `compute_envelope`

For MODERATE and HEAVY tiles only:
1. `compute_envelope(object_name, grid_res=3.0, height_threshold=4.0)`
2. `separate_loose(object_name, keep_largest=True)` - post-envelope cleanup
3. `save_file()`

Parameters:
- `grid_res=3.0` - ray grid spacing in meters (smaller = more precise, slower)
- `height_threshold=4.0` - faces this far above ground are canopy

## Phase 4: Re-Classification

**Tool:** `classify_surfaces`

1. `classify_surfaces(object_name)` on all processed tiles
2. Verify canopy is now < 2% on all tiles
3. If any tile still > 5%: flag for manual review
4. Surface groups are now ready for per-group operations

## Phase 5: UV Projection

**Tool:** `project_uv`

1. `project_uv(object_name, direction="top_down")` on all tiles
2. Verify UV layer was created
3. `save_file()`

## Phase 6: Optimization (Optional)

**Tool:** `decimate_mesh`

Only if tiles exceed target face count:
1. Target: 500k-2M faces per tile
2. For tiles > 2M faces:
   - `decimate_mesh(object_name, target_count=1000000)`
3. `save_file()`

## Workflow Summary

```
For each tile:
  Phase 1: classify_surfaces -> determine category

  If SKIP: go to Phase 5
  If MARGINAL: Phase 2 -> Phase 4 -> Phase 5
  If MODERATE: Phase 2 -> Phase 3 -> Phase 4 -> Phase 5
  If HEAVY: Phase 2 -> Phase 3 -> Phase 4 -> check if < 5% -> Phase 5

  Phase 6: if faces > 2M

  save_file after every phase
```

## Common Pitfalls

- **Removing terrain faces**: If normal_threshold is too aggressive, you'll cut into hillsides. Start conservative (< -0.2).
- **Envelope on sparse meshes**: If the tile has large gaps, the raycasting grid may miss ground. Use smaller grid_res.
- **Timeout on large tiles**: Tiles with > 4M faces may timeout during envelope. Process these individually.
- **Order matters**: Always do basic cleanup before envelope. Envelope is expensive and works better on pre-cleaned meshes.
