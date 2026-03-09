"""Activity logger — append-only JSONL log of sidecar actions."""
from datetime import datetime, timezone
from pathlib import Path

from cmdop_claude.models.sidecar import ActivityEntry

_MAX_LINES = 1000
_KEEP_LINES = 500


class ActivityLogger:
    """Reads and writes .claude/.sidecar/activity.jsonl.

    Auto-rotates: when the file exceeds 1000 lines, trims to the last 500.
    """

    def __init__(self, sidecar_dir: Path) -> None:
        self._log_file = sidecar_dir / "activity.jsonl"

    def log(
        self, action: str, tokens: int = 0, model: str = "", **details: object
    ) -> None:
        entry = ActivityEntry(
            ts=datetime.now(tz=timezone.utc),
            action=action,
            tokens=tokens,
            model=model,
            details=details,
        )
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        self._rotate()

    def _rotate(self) -> None:
        try:
            lines = self._log_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            return
        if len(lines) > _MAX_LINES:
            self._log_file.write_text(
                "\n".join(lines[-_KEEP_LINES:]) + "\n", encoding="utf-8"
            )

    def read(self, limit: int = 20) -> list[ActivityEntry]:
        if not self._log_file.exists():
            return []
        lines = self._log_file.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(ActivityEntry.model_validate_json(line))
            except Exception:
                continue
        return entries

    def last_action_age(self, action: str) -> float | None:
        """Seconds since last occurrence of `action`, or None if never ran."""
        if not self._log_file.exists():
            return None
        lines = self._log_file.read_text(encoding="utf-8").strip().splitlines()
        for line in reversed(lines):
            try:
                entry = ActivityEntry.model_validate_json(line)
                if entry.action == action:
                    delta = datetime.now(tz=timezone.utc) - entry.ts
                    return delta.total_seconds()
            except Exception:
                continue
        return None
