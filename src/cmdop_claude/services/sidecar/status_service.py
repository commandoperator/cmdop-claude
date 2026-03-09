"""StatusService — status reporting and map access."""
from __future__ import annotations

from datetime import datetime, timezone

from cmdop_claude.models.sidecar.status import SidecarStatus

from .state import SidecarState


class StatusService:
    def __init__(self, state: SidecarState) -> None:
        self._s = state

    def get_status(self) -> SidecarStatus:
        review_path = self._s.sidecar_dir / "review.md"
        last_run: datetime | None = None
        pending = 0

        if review_path.exists():
            last_run = datetime.fromtimestamp(
                review_path.stat().st_mtime, tz=timezone.utc
            )
            try:
                text = review_path.read_text(encoding="utf-8")
                pending = text.count("(id: ")
            except Exception:
                pass

        suppressed = self._s.load_suppressed()
        tokens_today = 0
        cost_today = 0.0

        data = self._s.load_usage()
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        if data.get("date") == today:
            tokens_today = data.get("tokens", 0)
            cost_today = tokens_today * 0.00000025

        return SidecarStatus(
            enabled=True,
            last_run=last_run,
            pending_items=pending,
            suppressed_items=len(suppressed),
            tokens_today=tokens_today,
            cost_today_usd=round(cost_today, 6),
        )

    def generate_map(self):
        mapper = self._s.get_mapper()
        result = mapper.generate()
        self._s.track_usage(result.tokens_used)
        self._s.log_activity(
            "map", tokens=result.tokens_used, model=result.model_used,
            directories=len(result.directories),
            entry_points=len(result.entry_points),
        )
        return result

    def get_current_map(self) -> str:
        mapper = self._s.get_mapper()
        return mapper.get_current_map()
