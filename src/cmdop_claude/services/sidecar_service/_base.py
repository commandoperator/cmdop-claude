"""Sidecar service — shared state, lock, scan."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
import logging

from sdkrouter import SDKRouter

if TYPE_CHECKING:
    from ...sidecar.mapper import ProjectMapper
    from ...sidecar.tasks import TaskManager
from sdkrouter._constants import HOMEPAGE_URL

from ..._config import Config

logger = logging.getLogger(__name__)

_SDKROUTER_HELP = (
    f"Get your API key at {HOMEPAGE_URL} → set SDKROUTER_API_KEY env variable. "
    "Sidecar LLM features (review, fix, map, init) require a valid key."
)
from ...models.sidecar import ActivityEntry, DocScanResult
from ...sidecar.activity import ActivityLogger
from ...sidecar.scanner import full_scan
from ..base import BaseService


class SidecarBase(BaseService):
    """Shared state and utilities for sidecar service mixins."""

    __slots__ = (
        "_sdk",
        "_sidecar_dir",
        "_claude_dir",
        "_usage_file",
        "_suppress_file",
        "_mapper",
        "_task_mgr",
        "_model",
        "_activity",
    )

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._claude_dir = Path(config.claude_dir_path)
        self._sidecar_dir = self._claude_dir / ".sidecar"
        self._usage_file = self._sidecar_dir / "usage.json"
        self._suppress_file = self._sidecar_dir / "suppressed.json"
        if not config.sdkrouter_api_key:
            logger.debug("SDKROUTER_API_KEY not set. %s", _SDKROUTER_HELP)
        self._sdk = SDKRouter(api_key=config.sdkrouter_api_key)
        self._model = config.sidecar_model
        self._mapper: "ProjectMapper | None" = None
        self._task_mgr: "TaskManager | None" = None
        self._activity = ActivityLogger(self._sidecar_dir)

    def _get_mapper(self) -> "ProjectMapper":
        if self._mapper is None:
            from ...sidecar.mapper import ProjectMapper

            project_root = self._claude_dir.parent
            self._mapper = ProjectMapper(self._sdk, project_root, self._sidecar_dir, self._model)
        return self._mapper

    def _get_task_manager(self) -> "TaskManager":
        if self._task_mgr is None:
            from ...sidecar.tasks import TaskManager

            self._task_mgr = TaskManager(self._sidecar_dir / "tasks")
        return self._task_mgr

    def _ensure_dirs(self) -> None:
        self._sidecar_dir.mkdir(parents=True, exist_ok=True)
        (self._sidecar_dir / "history").mkdir(exist_ok=True)

    # ── Lock ──────────────────────────────────────────────────────────

    def _acquire_lock(self) -> bool:
        lock = self._sidecar_dir / ".lock"
        if lock.exists():
            age = time.time() - lock.stat().st_mtime
            if age < 60:
                return False
        self._ensure_dirs()
        lock.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def _release_lock(self) -> None:
        lock = self._sidecar_dir / ".lock"
        if lock.exists():
            lock.unlink()

    # ── Scan ──────────────────────────────────────────────────────────

    def scan(self) -> DocScanResult:
        """Collect all documentation metadata. No LLM call."""
        return full_scan(self._claude_dir)

    # ── Suppression ───────────────────────────────────────────────────

    def _load_suppressed(self) -> dict[str, str]:
        if not self._suppress_file.exists():
            return {}
        try:
            data = json.loads(self._suppress_file.read_text(encoding="utf-8"))
            now = datetime.now(tz=timezone.utc).isoformat()
            return {k: v for k, v in data.items() if v > now}
        except Exception:
            return {}

    def acknowledge(self, item_id: str, days: int = 30) -> None:
        """Suppress a review item for N days."""
        self._ensure_dirs()
        suppressed = self._load_suppressed()
        expires = datetime.fromtimestamp(
            time.time() + days * 86400, tz=timezone.utc
        ).isoformat()
        suppressed[item_id] = expires
        self._suppress_file.write_text(
            json.dumps(suppressed, indent=2), encoding="utf-8"
        )

    # ── Usage tracking ────────────────────────────────────────────────

    def _track_usage(self, tokens: int) -> None:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        data: dict = {}
        if self._usage_file.exists():
            try:
                data = json.loads(self._usage_file.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if data.get("date") != today:
            data = {"date": today, "tokens": 0, "calls": 0}
        data["tokens"] = data.get("tokens", 0) + tokens
        data["calls"] = data.get("calls", 0) + 1
        self._usage_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    # ── Activity log ───────────────────────────────────────────────────

    def _log_activity(
        self, action: str, tokens: int = 0, model: str = "", **details: object
    ) -> None:
        self._activity.log(action, tokens=tokens, model=model or self._model, **details)

    def get_activity(self, limit: int = 20) -> list[ActivityEntry]:
        return self._activity.read(limit=limit)

    def last_action_age(self, action: str) -> float | None:
        return self._activity.last_action_age(action)
