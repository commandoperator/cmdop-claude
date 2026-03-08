"""Sidecar status and map access."""
import json
from datetime import datetime, timezone

from ...models.sidecar import SidecarStatus
from ._base import SidecarBase


class StatusMixin(SidecarBase):
    """Status reporting and map access."""

    def get_status(self) -> SidecarStatus:
        """Return current sidecar state."""
        review_path = self._sidecar_dir / "review.md"
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

        suppressed = self._load_suppressed()
        tokens_today = 0
        cost_today = 0.0

        if self._usage_file.exists():
            try:
                data = json.loads(self._usage_file.read_text(encoding="utf-8"))
                today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
                if data.get("date") == today:
                    tokens_today = data.get("tokens", 0)
                    cost_today = tokens_today * 0.00000025
            except Exception:
                pass

        return SidecarStatus(
            enabled=True,
            last_run=last_run,
            pending_items=pending,
            suppressed_items=len(suppressed),
            tokens_today=tokens_today,
            cost_today_usd=round(cost_today, 6),
        )

    def generate_map(self):
        """Generate or update the project map."""
        mapper = self._get_mapper()
        result = mapper.generate()
        self._track_usage(result.tokens_used)
        self._log_activity(
            "map", tokens=result.tokens_used, model=result.model_used,
            directories=len(result.directories),
            entry_points=len(result.entry_points),
        )
        return result

    def get_current_map(self) -> str:
        """Return current project-map.md content, or empty string."""
        mapper = self._get_mapper()
        return mapper.get_current_map()
