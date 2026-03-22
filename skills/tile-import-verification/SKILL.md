---
name: tile-import-verification
description: Step-by-step verification of PLY tile imports from Metashape - naming, transforms, bounding boxes, and grid coverage.
---

# Tile Import Verification

## Overview

Verifies that tiles imported from Metashape are correct before processing begins. Catches naming violations, transform issues, and missing tiles early.

## Pre-Flight Checklist

- [ ] PLY directory path confirmed
- [ ] Expected tile count known (from Metashape export)
- [ ] Metashape chunk bounds available for comparison (optional)

## Workflow

### Step 1: Import Tiles
1. Call `batch_import(directory="/path/to/ply/dir", format="ply")`
2. Record the per-tile results and tile grid summary

### Step 2: Verify Naming
1. Check every imported object follows `Tile_X-Y` naming
2. If any objects have non-standard names, rename them to match the filename

### Step 3: Verify Identity Transforms
1. For each tile, check `identity_transform` from import results
2. ALL tiles MUST have identity transforms
3. If any don't: DO NOT PROCEED - transforms must be fixed first

### Step 4: Verify Bounding Boxes
1. Call `get_mesh_stats` on each tile
2. Check bounding box dimensions are reasonable (not degenerate)
3. If Metashape chunk bounds are available, compare:
   - Tile bounding boxes should fit within chunk bounds
   - Total coverage should roughly match chunk extent
4. Check for overlapping tiles (bounding boxes that intersect significantly)

### Step 5: Grid Coverage
1. Review tile grid summary
2. Report grid dimensions (NxM)
3. Report any gaps (missing tiles in the grid)
4. Gaps are warnings, not blockers

### Step 6: Save
1. `save_file` after successful verification

## Pass/Fail Criteria

**PASS** if:
- All tiles named Tile_X-Y
- All tiles have identity transforms
- All tiles have > 1000 faces
- No degenerate bounding boxes

**FAIL** if:
- Any tile has non-identity transform
- Any tile has 0 faces
- Import errors on any file

## Common Pitfalls

- **Wrong CRS in Metashape export**: Tiles may be 1000x too large or too small. Check bounding box dimensions are in meters.
- **FBX axis confusion**: If importing FBX instead of PLY, axis convention may cause rotation. Always prefer PLY for the initial import.
- **Duplicate names**: Blender appends .001 to duplicate names. If this happens, the source files may have naming conflicts.
