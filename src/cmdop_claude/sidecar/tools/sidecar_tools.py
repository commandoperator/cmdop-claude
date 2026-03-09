"""MCP tools: sidecar_* (12 tools)."""
from __future__ import annotations

from cmdop_claude._config import get_config
from cmdop_claude.services.sidecar import SidecarService

_service: SidecarService | None = None


def _get_service() -> SidecarService:
    global _service
    if _service is None:
        _service = SidecarService(get_config())
    return _service


def sidecar_scan() -> str:
    """Scan .claude/ documentation for staleness, contradictions, and gaps.

    Reads all doc files, git log, dependencies, and directory structure.
    Sends metadata to a cheap LLM for analysis.
    Writes review to .claude/.sidecar/review.md.

    Returns a summary of found issues.
    """
    svc = _get_service()
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
    svc = _get_service()
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
    svc = _get_service()
    content = svc.get_current_review()
    return content or "No review available. Run sidecar_scan first."


def sidecar_acknowledge(item_id: str, days: int = 30) -> str:
    """Suppress a sidecar review item for N days.

    Args:
        item_id: The item ID from the review (shown in parentheses).
        days: Number of days to suppress. Default 30.
    """
    svc = _get_service()
    svc.acknowledge(item_id, days)
    return f"Suppressed {item_id} for {days} days."


def sidecar_map() -> str:
    """Generate or update the project structure map.

    Scans directories, annotates with LLM, writes .claude/project-map.md.
    Uses annotation cache — only changed directories trigger LLM calls.

    Returns a summary of the generated map.
    """
    svc = _get_service()
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
    svc = _get_service()
    content = svc.get_current_map()
    return content or "No project map available. Run sidecar_map first."


def sidecar_tasks(status: str = "") -> str:
    """List sidecar tasks, optionally filtered by status.

    Args:
        status: Filter by status (pending, in_progress, completed, dismissed).
                Leave empty to list all tasks.
    """
    svc = _get_service()
    tasks = svc.list_tasks(status=status or None)

    if not tasks:
        return "No tasks found."

    lines = [f"Tasks ({len(tasks)}):"]
    for t in tasks:
        lines.append(f"- [{t.priority}] {t.title} (id: {t.id}, status: {t.status})")
        if t.context_files:
            lines.append(f"  Files: {', '.join(t.context_files)}")
    return "\n".join(lines)


def sidecar_task_update(task_id: str, status: str) -> str:
    """Update a task's status.

    Args:
        task_id: Task ID (e.g. T-001).
        status: New status: pending, in_progress, completed, dismissed.
    """
    svc = _get_service()
    updated = svc.update_task_status(task_id, status)
    if updated:
        return f"Task {task_id} updated to {status}."
    return f"Task {task_id} not found."


def sidecar_task_create(
    title: str,
    description: str,
    priority: str = "medium",
    context_files: list[str] | None = None,
) -> str:
    """Create a new manual task.

    Args:
        title: Short task title.
        description: Detailed description (markdown supported).
        priority: Priority level: critical, high, medium, low. Default: medium.
        context_files: Optional list of relevant file paths.
    """
    svc = _get_service()
    task = svc.create_task(
        title=title,
        description=description,
        priority=priority,
        context_files=context_files,
    )
    return f"Created task {task.id}: {task.title} [{task.priority}]"


def sidecar_fix(task_id: str, apply: bool = False) -> str:
    """Generate a fix for a pending documentation task.

    Reads the task, generates updated file content via LLM,
    and returns the diff. Set apply=True to write the fix.

    Args:
        task_id: Task ID (e.g. T-001).
        apply: If True, write the fix to disk and mark task completed.
    """
    svc = _get_service()
    result = svc.fix_task(task_id, apply=apply)

    if result.diff == "Task not found.":
        return f"Task {task_id} not found."

    lines = [f"Fix for {result.file_path}:", ""]
    if result.diff == "(no changes needed)":
        lines.append("No changes needed.")
    else:
        lines.append("```diff")
        lines.append(result.diff)
        lines.append("```")

    if result.applied:
        lines.append(f"\nApplied. Task {task_id} marked completed.")
    elif result.diff != "(no changes needed)":
        lines.append(f"\nDry run. Call sidecar_fix('{task_id}', apply=True) to apply.")

    lines.append(f"Tokens: {result.tokens_used}")
    return "\n".join(lines)


def sidecar_init() -> str:
    """Initialize .claude/ for a project that has no documentation.

    Scans the project (deps, dirs, git log, entry points) and generates
    CLAUDE.md + rules files tailored to the detected tech stack.

    Skips if CLAUDE.md already exists with content.
    """
    svc = _get_service()
    result = svc.init_project()

    if not result.files_created:
        return f"Skipped: {result.model_used}"

    lines = [f"Initialized {len(result.files_created)} files:"]
    for f in result.files_created:
        lines.append(f"  - {f}")
    lines.append(f"Model: {result.model_used} | Tokens: {result.tokens_used}")
    return "\n".join(lines)


def sidecar_activity(limit: int = 20) -> str:
    """View recent sidecar activity log.

    Shows what actions the sidecar has performed: init, review, fix, map.
    Each entry includes timestamp, action, tokens used, and details.

    Args:
        limit: Number of recent entries to return. Default 20.
    """
    svc = _get_service()
    entries = svc.get_activity(limit=limit)

    if not entries:
        return "No activity recorded yet."

    lines = [f"Recent activity ({len(entries)} entries):"]
    for e in entries:
        detail_parts = [f"{k}={v}" for k, v in e.details.items()]
        detail_str = f" ({', '.join(detail_parts)})" if detail_parts else ""
        lines.append(
            f"- [{e.ts.strftime('%Y-%m-%d %H:%M')}] {e.action} "
            f"| {e.tokens} tokens{detail_str}"
        )
    return "\n".join(lines)


def register(mcp) -> None:
    """Register all sidecar tools with the FastMCP instance."""
    mcp.tool()(sidecar_scan)
    mcp.tool()(sidecar_status)
    mcp.tool()(sidecar_review)
    mcp.tool()(sidecar_acknowledge)
    mcp.tool()(sidecar_map)
    mcp.tool()(sidecar_map_view)
    mcp.tool()(sidecar_tasks)
    mcp.tool()(sidecar_task_update)
    mcp.tool()(sidecar_task_create)
    mcp.tool()(sidecar_fix)
    mcp.tool()(sidecar_init)
    mcp.tool()(sidecar_activity)
