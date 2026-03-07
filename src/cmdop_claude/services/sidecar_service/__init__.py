"""Sidecar service — documentation librarian.

Composed from domain-specific mixins:
- _base: shared state, lock, scan, suppression, usage tracking
- _review: generate review, write review.md
- _mcp: register/unregister MCP server
- _tasks: task CRUD
- _fix: generate LLM fix for a task
- _init: generate initial .claude/ files
- _status: status reporting, map access
"""
from ._base import SidecarBase
from ._fix import FixMixin
from ._init import InitMixin
from ._mcp import MCPMixin
from ._review import ReviewMixin
from ._status import StatusMixin
from ._tasks import TasksMixin


class SidecarService(
    ReviewMixin,
    MCPMixin,
    TasksMixin,
    FixMixin,
    InitMixin,
    StatusMixin,
    SidecarBase,
):
    """Documentation librarian that scans .claude/ and produces review reports."""


__all__ = ["SidecarService"]
