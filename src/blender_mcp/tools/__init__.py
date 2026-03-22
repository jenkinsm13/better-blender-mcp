"""Tool registration for all Blender MCP tools."""

from blender_mcp.tools import (
    scene,
    mesh,
    import_export,
    viewport,
    modifiers,
    transforms,
    project,
)

_MODULES = [scene, mesh, import_export, viewport, modifiers, transforms, project]


def register_all_tools(mcp) -> None:
    """Register all tool modules with the MCP server."""
    for module in _MODULES:
        module.register(mcp)
