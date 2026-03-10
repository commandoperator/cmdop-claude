"""Programmatic injection of the ## Workflow section into CLAUDE.md.

Instead of relying on the LLM to include sidecar tool instructions,
we inject them deterministically after generation.
"""
from __future__ import annotations

import re

_SIDECAR_WORKFLOW_TEMPLATE = """\
## Workflow

*   Before starting complex tasks, check `.claude/plans/` for existing plans and save new plans there
*   Periodically use `sidecar_tasks` MCP tool to check pending tasks (do NOT use built-in TaskList — it is unrelated)
*   Sidecar MCP tools (`sidecar_tasks`, `sidecar_scan`, `sidecar_map`, `docs_search`, `docs_get`, `docs_list`, `docs_reindex`, `mcp_list_servers`, `changelog_list`, `changelog_get`) are called directly — they are NOT deferred tools, do NOT search for them via ToolSearch
*   After major changes, use sidecar tools: `sidecar_scan` to review docs, `sidecar_map` to update project map
*   Read `.claude/rules/` for project-specific coding guidelines before making changes
*   Keep CLAUDE.md under 200 lines — move detailed rules to `.claude/rules/*.md`
*   When working with external APIs, databases, browsers, or new tools — check if a relevant MCP plugin exists: use `mcp_list_servers` to see what's configured, or `sidecar_tasks` to browse plugins via `make -C .claude dashboard` (Plugin Browser tab)
*   Changelog files live in `.claude/changelog/` — use `/commit` skill on every release (writes `.claude/changelog/vX.Y.Z.md`, bumps version, commits, tags){docs_hint}{packages_hint}
"""

# Regex: matches "## Workflow" heading up to the next "##" heading (or EOF)
_WORKFLOW_RE = re.compile(
    r"(^##\s+Workflow\s*\n)(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def inject_sidecar_workflow(
    content: str,
    docs_workflow_hint: str = "",
    packages_hint: str = "",
) -> str:
    """Replace or insert ## Workflow section with canonical sidecar instructions.

    Args:
        content: Full CLAUDE.md text.
        docs_workflow_hint: Optional hint about configured docsPaths sources.
        packages_hint: Optional hint about configured packagesPaths sources.

    Returns:
        Updated CLAUDE.md text.
    """
    docs_hint = f"\n*   {docs_workflow_hint}" if docs_workflow_hint else ""
    packages_hint_str = f"\n*   {packages_hint}" if packages_hint else ""

    section = _SIDECAR_WORKFLOW_TEMPLATE.format(
        docs_hint=docs_hint,
        packages_hint=packages_hint_str,
    )

    if _WORKFLOW_RE.search(content):
        # Replace the entire ## Workflow block (heading + body) with canonical version
        content = _WORKFLOW_RE.sub(section, content, count=1)
    else:
        # No ## Workflow found — insert before ## Key Rules if present, else append
        key_rules_match = re.search(r"^##\s+Key Rules", content, re.MULTILINE)
        if key_rules_match:
            pos = key_rules_match.start()
            content = content[:pos] + section + "\n" + content[pos:]
        else:
            content = content.rstrip() + "\n\n" + section

    return content
