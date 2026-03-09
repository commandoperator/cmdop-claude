"""Shared sidecar state — injected into all domain services."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sdkrouter import SDKRouter
from sdkrouter._constants import HOMEPAGE_URL

from cmdop_claude._config import Config
from cmdop_claude.infrastructure.llm import LLMCaller
from cmdop_claude.infrastructure.storage import JSONStorage
from cmdop_claude.models.sidecar.scan import DocScanResult
from cmdop_claude.sidecar.activity import ActivityLogger
from cmdop_claude.sidecar.scanner import full_scan

if TYPE_CHECKING:
    from cmdop_claude.sidecar.mapper import ProjectMapper
    from cmdop_claude.sidecar.tasks import TaskManager

logger = logging.getLogger(__name__)

_SDKROUTER_HELP = (
    f"Get your API key at {HOMEPAGE_URL} → set SDKROUTER_API_KEY env variable. "
    "Sidecar LLM features (review, fix, map, init) require a valid key."
)


class SidecarState:
    """Shared state injected into sidecar domain services."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.claude_dir = Path(config.claude_dir_path)
        self.sidecar_dir = self.claude_dir / ".sidecar"
        self.usage_file = self.sidecar_dir / "usage.json"
        self.suppress_file = self.sidecar_dir / "suppressed.json"

        if not config.sdkrouter_api_key:
            logger.debug("SDKROUTER_API_KEY not set. %s", _SDKROUTER_HELP)

        self.sdk = SDKRouter(api_key=config.sdkrouter_api_key)
        self.llm = LLMCaller(self.sdk)
        self.model = config.sidecar_model
        self.activity = ActivityLogger(self.sidecar_dir)

        self._usage_storage = JSONStorage(self.usage_file)
        self._suppress_storage = JSONStorage(self.suppress_file)

        self._mapper: ProjectMapper | None = None
        self._task_mgr: TaskManager | None = None

    # ── Dirs ──────────────────────────────────────────────────────────

    def ensure_dirs(self) -> None:
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        (self.sidecar_dir / "history").mkdir(exist_ok=True)

    # ── Lock ──────────────────────────────────────────────────────────

    def acquire_lock(self) -> bool:
        lock = self.sidecar_dir / ".lock"
        if lock.exists():
            age = time.time() - lock.stat().st_mtime
            if age < 60:
                return False
        self.ensure_dirs()
        lock.write_text(str(os.getpid()), encoding="utf-8")
        return True

    def release_lock(self) -> None:
        lock = self.sidecar_dir / ".lock"
        if lock.exists():
            lock.unlink()

    # ── Scan ──────────────────────────────────────────────────────────

    def scan(self) -> DocScanResult:
        return full_scan(self.claude_dir)

    # ── Suppression ───────────────────────────────────────────────────

    def load_suppressed(self) -> dict[str, str]:
        data = self._suppress_storage.load_dict()
        now = datetime.now(tz=timezone.utc).isoformat()
        return {k: v for k, v in data.items() if isinstance(v, str) and v > now}

    def save_suppressed(self, suppressed: dict[str, str]) -> None:
        self._suppress_storage.save_dict(suppressed)

    def acknowledge(self, item_id: str, days: int = 30) -> None:
        self.ensure_dirs()
        suppressed = self.load_suppressed()
        expires = datetime.fromtimestamp(
            time.time() + days * 86400, tz=timezone.utc
        ).isoformat()
        suppressed[item_id] = expires
        self.save_suppressed(suppressed)

    # ── Usage tracking ────────────────────────────────────────────────

    def track_usage(self, tokens: int) -> None:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        data = self._usage_storage.load_dict()
        if data.get("date") != today:
            data = {"date": today, "tokens": 0, "calls": 0}
        data["tokens"] = data.get("tokens", 0) + tokens
        data["calls"] = data.get("calls", 0) + 1
        self._usage_storage.save_dict(data)

    def load_usage(self) -> dict:
        return self._usage_storage.load_dict()

    # ── Activity log ──────────────────────────────────────────────────

    def log_activity(
        self, action: str, tokens: int = 0, model: str = "", **details: object
    ) -> None:
        self.activity.log(action, tokens=tokens, model=model or self.model, **details)

    # ── Lazy sub-services ─────────────────────────────────────────────

    def get_mapper(self) -> ProjectMapper:
        if self._mapper is None:
            from cmdop_claude.sidecar.mapper import ProjectMapper
            project_root = self.claude_dir.parent
            self._mapper = ProjectMapper(self.sdk, project_root, self.sidecar_dir, self.model)
        return self._mapper

    def get_task_manager(self) -> TaskManager:
        if self._task_mgr is None:
            from cmdop_claude.sidecar.tasks import TaskManager
            self._task_mgr = TaskManager(self.sidecar_dir / "tasks")
        return self._task_mgr
