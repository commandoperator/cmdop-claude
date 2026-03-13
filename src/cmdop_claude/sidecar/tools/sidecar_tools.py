"""Compatibility shim — re-exports all tools from sub-modules.

Import individual tools from their respective modules for new code:
  - review_tools: sidecar_scan, sidecar_status, sidecar_review, sidecar_acknowledge
  - map_tools:    sidecar_map, sidecar_map_view
  - task_tools:   sidecar_tasks, sidecar_task_update, sidecar_task_create, sidecar_fix
  - init_tools:   sidecar_init, sidecar_add_rule, sidecar_activity
  - changelog_tools: changelog_list, changelog_get
"""
from __future__ import annotations

from cmdop_claude.sidecar.tools.review_tools import (
    sidecar_scan,
    sidecar_status,
    sidecar_review,
    sidecar_acknowledge,
)
from cmdop_claude.sidecar.tools.map_tools import (
    sidecar_map,
    sidecar_map_view,
)
from cmdop_claude.sidecar.tools.task_tools import (
    sidecar_tasks,
    sidecar_task_update,
    sidecar_task_create,
    sidecar_fix,
)
from cmdop_claude.sidecar.tools.init_tools import (
    sidecar_init,
    sidecar_add_rule,
    sidecar_activity,
)
from cmdop_claude.sidecar.tools.changelog_tools import (
    changelog_list,
    changelog_get,
)

from cmdop_claude.sidecar.tools import review_tools, map_tools, task_tools, init_tools, changelog_tools

__all__ = [
    "sidecar_scan",
    "sidecar_status",
    "sidecar_review",
    "sidecar_acknowledge",
    "sidecar_map",
    "sidecar_map_view",
    "sidecar_tasks",
    "sidecar_task_update",
    "sidecar_task_create",
    "sidecar_fix",
    "sidecar_init",
    "sidecar_add_rule",
    "sidecar_activity",
    "changelog_list",
    "changelog_get",
]


def register(mcp) -> None:
    """Register all sidecar tools with the FastMCP instance."""
    review_tools.register(mcp)
    map_tools.register(mcp)
    task_tools.register(mcp)
    init_tools.register(mcp)
    changelog_tools.register(mcp)
