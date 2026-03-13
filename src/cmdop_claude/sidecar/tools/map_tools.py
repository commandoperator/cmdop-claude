"""MCP tools: sidecar_map, sidecar_map_view."""
from __future__ import annotations

from cmdop_claude.sidecar.tools._service_registry import get_service


def sidecar_map() -> str:
    """Generate or update the project structure map.

    Scans directories, annotates with LLM, writes .claude/project-map.md.
    Uses annotation cache — only changed directories trigger LLM calls.

    Returns a summary of the generated map.
    """
    svc = get_service()
    try:
        result = svc.generate_map()
    except Exception as e:
        return f"Error generating map: {e}"

    return (
        f"Project map updated: {len(result.directories)} directories, "
        f"{len(result.entry_points)} entry points.\n"
        f"Type: {result.project_type}\n"
        f"Tokens used: {result.tokens_used} ({result.model_used})"
    )


def sidecar_map_view() -> str:
    """Read the current project map without regenerating.

    Returns the contents of .claude/project-map.md if it exists.
    This is free (no LLM call). Use sidecar_map to generate a fresh map.
    """
    svc = get_service()
    content = svc.get_current_map()
    return content or "No project map available. Run sidecar_map first."


def register(mcp) -> None:
    """Register map tools with the FastMCP instance."""
    mcp.tool()(sidecar_map)
    mcp.tool()(sidecar_map_view)
