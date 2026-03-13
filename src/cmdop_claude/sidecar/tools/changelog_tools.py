"""MCP tools: changelog_list, changelog_get."""
from __future__ import annotations

from pathlib import Path

from cmdop_claude._config import get_config
from cmdop_claude.services.changelog import ChangelogService


def _get_changelog_service() -> ChangelogService:
    config = get_config()
    changelog_dir = Path(config.claude_dir_path) / "changelog"
    return ChangelogService(changelog_dir)


def changelog_list(limit: int = 10) -> str:
    """List recent cmdop-claude releases.

    Args:
        limit: Number of entries to return. Default 10.
    """
    svc = _get_changelog_service()
    entries = svc.list_entries(limit=limit)
    if not entries:
        return "No changelog entries found."
    lines = []
    for e in entries:
        date_str = e.release_date.isoformat() if e.release_date else "unknown"
        lines.append(f"v{e.version} — {e.title} ({date_str})")
    return "\n".join(lines)


def changelog_get(version: str = "latest") -> str:
    """Get full changelog entry for a specific version (or 'latest').

    Args:
        version: Version string like '0.1.63' or 'v0.1.63'. Use 'latest' for most recent.
    """
    svc = _get_changelog_service()
    if version == "latest":
        entry = svc.get_latest()
    else:
        entry = svc.get_entry(version)
    if not entry:
        return f"No changelog entry found for '{version}'."
    return f"# v{entry.version} — {entry.title}\n\n{entry.content}"


def register(mcp) -> None:
    """Register changelog tools with the FastMCP instance."""
    mcp.tool()(changelog_list)
    mcp.tool()(changelog_get)
