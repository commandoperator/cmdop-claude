"""MCP tool handlers, split by domain."""
from cmdop_claude.sidecar.tools import review_tools, map_tools, task_tools, init_tools, changelog_tools
from cmdop_claude.sidecar.tools.review_tools import register as register_review
from cmdop_claude.sidecar.tools.map_tools import register as register_map
from cmdop_claude.sidecar.tools.task_tools import register as register_tasks
from cmdop_claude.sidecar.tools.init_tools import register as register_init
from cmdop_claude.sidecar.tools.changelog_tools import register as register_changelog

__all__ = [
    "review_tools",
    "map_tools",
    "task_tools",
    "init_tools",
    "changelog_tools",
    "register_review",
    "register_map",
    "register_tasks",
    "register_init",
    "register_changelog",
]
