"""Sidecar domain services.

SidecarService is now a thin facade that delegates to independent domain services.
Each service can be used directly for testing or composition.
"""
from cmdop_claude._config import Config

from .fix_service import FixService
from .init_service import InitService
from .mcp_reg_service import MCPRegService, save_api_key
from .review_service import ReviewService
from .state import SidecarState
from .status_service import StatusService
from .task_service import TaskService


class SidecarService:
    """Thin facade over domain services — maintains backward-compatible API."""

    def __init__(self, config: Config) -> None:
        state = SidecarState(config)
        self._state = state
        # Expose SDK for callers that need it directly (e.g. docs_reindex)
        self._sdk = state.sdk

        self._review = ReviewService(state)
        self._fix = FixService(state)
        self._init = InitService(state)
        self._tasks = TaskService(state)
        self._mcp = MCPRegService(state)
        self._status = StatusService(state)

    # ── Review ────────────────────────────────────────────────────────

    def generate_review(self, scan_result=None):
        return self._review.generate_review(scan_result)

    def get_current_review(self) -> str:
        return self._review.get_current_review()

    # ── Scan / Acknowledge ────────────────────────────────────────────

    def scan(self):
        return self._state.scan()

    def acknowledge(self, item_id: str, days: int = 30) -> None:
        self._state.acknowledge(item_id, days)

    # ── Fix ───────────────────────────────────────────────────────────

    def fix_task(self, task_id: str, apply: bool = False):
        return self._fix.fix_task(task_id, apply=apply)

    # ── Init ──────────────────────────────────────────────────────────

    def init_project(self):
        return self._init.init_project()

    # ── Tasks ─────────────────────────────────────────────────────────

    def list_tasks(self, status=None):
        return self._tasks.list_tasks(status=status)

    def create_task(self, title: str, description: str, priority: str = "medium", context_files=None):
        return self._tasks.create_task(title, description, priority, context_files)

    def update_task_status(self, task_id: str, status: str) -> bool:
        return self._tasks.update_task_status(task_id, status)

    def get_pending_summary(self, max_items: int = 3) -> str:
        return self._tasks.get_pending_summary(max_items)

    def convert_review_to_tasks(self, items):
        return self._tasks.convert_review_to_tasks(items)

    # ── MCP ───────────────────────────────────────────────────────────

    def register_mcp(self) -> bool:
        return self._mcp.register_mcp()

    def unregister_mcp(self) -> bool:
        return self._mcp.unregister_mcp()

    def is_mcp_registered(self) -> bool:
        return self._mcp.is_mcp_registered()

    def setup_project_hooks(self) -> list[str]:
        return self._mcp.setup_project_hooks()

    # ── Status / Map ──────────────────────────────────────────────────

    def get_status(self):
        return self._status.get_status()

    def generate_map(self):
        return self._status.generate_map()

    def get_current_map(self) -> str:
        return self._status.get_current_map()

    # ── State accessors (for tests and hooks that inspect internals) ──

    @property
    def _sidecar_dir(self):
        return self._state.sidecar_dir

    @property
    def _claude_dir(self):
        return self._state.claude_dir

    @property
    def _usage_file(self):
        return self._state.usage_file

    @property
    def _suppress_file(self):
        return self._state.suppress_file

    def _ensure_dirs(self):
        self._state.ensure_dirs()

    def _build_items(self, llm_items, suppressed):
        return self._review._build_items(llm_items, suppressed)

    def _write_review_md(self, result):
        self._review._write_review_md(result)

    def _load_suppressed(self):
        return self._state.load_suppressed()

    def _track_usage(self, tokens: int):
        self._state.track_usage(tokens)

    # ── Activity ──────────────────────────────────────────────────────

    def get_activity(self, limit: int = 20):
        return self._state.activity.read(limit=limit)

    def last_action_age(self, action: str):
        return self._state.activity.last_action_age(action)


__all__ = [
    "SidecarService",
    "SidecarState",
    "ReviewService",
    "FixService",
    "InitService",
    "TaskService",
    "MCPRegService",
    "StatusService",
    "save_api_key",
]
