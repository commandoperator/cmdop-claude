"""MCP tools: sidecar_tasks, sidecar_task_update, sidecar_task_create, sidecar_fix."""
from __future__ import annotations

from cmdop_claude.sidecar.tools._service_registry import get_service


def sidecar_tasks(status: str = "") -> str:
    """List sidecar tasks, optionally filtered by status.

    Args:
        status: Filter by status (pending, in_progress, completed, dismissed).
                Leave empty to list all tasks.
    """
    svc = get_service()
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
    svc = get_service()
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
    svc = get_service()
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
    svc = get_service()
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


def register(mcp) -> None:
    """Register task tools with the FastMCP instance."""
    mcp.tool()(sidecar_tasks)
    mcp.tool()(sidecar_task_update)
    mcp.tool()(sidecar_task_create)
    mcp.tool()(sidecar_fix)
