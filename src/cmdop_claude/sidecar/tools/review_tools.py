"""MCP tools: sidecar_scan, sidecar_status, sidecar_review, sidecar_acknowledge."""
from __future__ import annotations

from cmdop_claude.sidecar.tools._service_registry import get_service


def sidecar_scan() -> str:
    """Scan .claude/ documentation for staleness, contradictions, and gaps.

    Reads all doc files, git log, dependencies, and directory structure.
    Sends metadata to a cheap LLM for analysis.
    Writes review to .claude/.sidecar/review.md.

    Returns a summary of found issues.
    """
    svc = get_service()
    try:
        result = svc.generate_review()
    except RuntimeError as e:
        return f"Skipped: {e}"

    if not result.items:
        return "No documentation issues found."

    lines = [f"Found {len(result.items)} issue(s):", ""]
    for item in result.items:
        sev = {"high": "!!!", "medium": "!!", "low": "!"}.get(item.severity, "!")
        lines.append(f"[{sev}] {item.category}: {item.description}")
        if item.affected_files:
            lines.append(f"    Files: {', '.join(item.affected_files)}")
        lines.append(f"    Action: {item.suggested_action}")
        lines.append("")

    lines.append("Full review: .claude/.sidecar/review.md")
    lines.append(f"Tokens used: {result.tokens_used} ({result.model_used})")
    return "\n".join(lines)


def sidecar_status() -> str:
    """Get sidecar status: last run time, pending items, suppressed items, token usage today."""
    svc = get_service()
    status = svc.get_status()
    lines = [
        f"Last run: {status.last_run.isoformat() if status.last_run else 'never'}",
        f"Pending items: {status.pending_items}",
        f"Suppressed items: {status.suppressed_items}",
        f"Tokens today: {status.tokens_today}",
        f"Cost today: ${status.cost_today_usd:.6f}",
    ]
    return "\n".join(lines)


def sidecar_review() -> str:
    """Read the current sidecar review without running a new scan.

    Returns the contents of .claude/.sidecar/review.md if it exists.
    This is free (no LLM call, no tokens). Use sidecar_scan to generate a fresh review.
    """
    svc = get_service()
    content = svc.get_current_review()
    return content or "No review available. Run sidecar_scan first."


def sidecar_acknowledge(item_id: str, days: int = 30) -> str:
    """Suppress a sidecar review item for N days.

    Args:
        item_id: The item ID from the review (shown in parentheses).
        days: Number of days to suppress. Default 30.
    """
    svc = get_service()
    svc.acknowledge(item_id, days)
    return f"Suppressed {item_id} for {days} days."


def register(mcp) -> None:
    """Register review tools with the FastMCP instance."""
    mcp.tool()(sidecar_scan)
    mcp.tool()(sidecar_status)
    mcp.tool()(sidecar_review)
    mcp.tool()(sidecar_acknowledge)
