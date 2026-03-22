"""Resource registration for Blender MCP resources."""

from blender_mcp.resources import scene_resources

_MODULES = [scene_resources]


def register_all_resources(mcp) -> None:
    """Register all resource modules with the MCP server."""
    for module in _MODULES:
        module.register(mcp)
