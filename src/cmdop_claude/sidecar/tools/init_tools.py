"""MCP tools: sidecar_init, sidecar_add_rule, sidecar_activity."""
from __future__ import annotations

from pathlib import Path

from cmdop_claude.sidecar.tools._service_registry import get_service


def sidecar_init() -> str:
    """Initialize .claude/ for a project that has no documentation.

    Scans the project (deps, dirs, git log, entry points) and generates
    CLAUDE.md + rules files tailored to the detected tech stack.

    Skips if CLAUDE.md already exists with content.
    """
    svc = get_service()
    result = svc.init_project()

    if not result.files_created:
        return f"Skipped: {result.model_used}"

    lines = [f"Initialized {len(result.files_created)} files:"]
    for f in result.files_created:
        lines.append(f"  - {f}")
    lines.append(f"Model: {result.model_used} | Tokens: {result.tokens_used}")
    return "\n".join(lines)


def sidecar_add_rule(
    filename: str,
    content: str,
    paths: list[str] | None = None,
) -> str:
    """Add or update a rule file in .claude/rules/.

    Use this to persist discovered coding patterns, conventions, or project-specific
    guidelines so they are available in future conversations.

    Args:
        filename: Rule filename, e.g. 'python.md' or 'api-conventions.md'.
                  Will be placed in .claude/rules/{filename}.
        content: Full markdown content of the rule. Should include a heading and
                 specific, actionable guidelines (not generic advice).
        paths: Optional list of glob patterns (e.g. ['**/*.py', 'src/**/*.py']).
               When provided, the rule is loaded lazily — only when Claude opens
               matching files, saving context tokens for unrelated work.
               Omit (or pass None) for rules that should always be loaded.

    Example:
        sidecar_add_rule(
            filename='api-conventions.md',
            content='# API Conventions\\n\\n- Always use snake_case for endpoints...',
            paths=['src/api/**/*.py', 'tests/api/**/*.py'],
        )
    """
    svc = get_service()
    rules_dir = svc._claude_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename — strip path separators, ensure .md extension
    safe_name = Path(filename).name
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    rule_path = rules_dir / safe_name
    already_exists = rule_path.exists()

    # Build frontmatter if paths provided
    from cmdop_claude.sidecar.scan._rules_templates import build_frontmatter
    frontmatter = build_frontmatter(paths) if paths else ""

    # If content already has frontmatter, use as-is; otherwise prepend ours
    normalized = content if content.startswith("---") else (frontmatter + content)
    if not normalized.endswith("\n"):
        normalized += "\n"

    rule_path.write_text(normalized, encoding="utf-8")
    action = "Updated" if already_exists else "Created"
    paths_info = f" (lazy — {len(paths)} path pattern(s))" if paths else " (always loaded)"
    return f"{action} .claude/rules/{safe_name}{paths_info}"


def sidecar_activity(limit: int = 20) -> str:
    """View recent sidecar activity log.

    Shows what actions the sidecar has performed: init, review, fix, map.
    Each entry includes timestamp, action, tokens used, and details.

    Args:
        limit: Number of recent entries to return. Default 20.
    """
    svc = get_service()
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
    """Register init tools with the FastMCP instance."""
    mcp.tool()(sidecar_init)
    mcp.tool()(sidecar_add_rule)
    mcp.tool()(sidecar_activity)
