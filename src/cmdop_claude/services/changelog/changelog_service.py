"""ChangelogService — read and write versioned changelog entries."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import ConfigDict

from cmdop_claude.models.base import CoreModel


_HEADER_RE = re.compile(r"^#\s+v(\S+)\s+[—–-]+\s+(.+)$", re.MULTILINE)
_DATE_RE = re.compile(r"^\*\*Date:\*\*\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse 'X.Y.Z' into sortable tuple. Returns (0,0,0) on failure."""
    try:
        parts = version.lstrip("v").split(".")
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return (0, 0, 0)


class ChangelogEntry(CoreModel):
    """A single changelog entry parsed from vX.Y.Z.md."""

    model_config = ConfigDict(extra="ignore")

    version: str
    title: str
    release_date: Optional[date] = None
    content: str  # full raw markdown (excluding the # header line)


class ChangelogService:
    """Reads and writes changelog/vX.Y.Z.md files.

    changelog_dir should point to the `changelog/` directory in the repo root.
    Falls back gracefully if the directory doesn't exist.
    """

    def __init__(self, changelog_dir: Path) -> None:
        self._dir = changelog_dir

    def list_entries(self, limit: int = 20) -> list[ChangelogEntry]:
        """Return changelog entries sorted by version descending."""
        if not self._dir.exists():
            return []
        entries: list[ChangelogEntry] = []
        for f in self._dir.glob("v*.md"):
            entry = self._parse_file(f)
            if entry:
                entries.append(entry)
        entries.sort(key=lambda e: _parse_semver(e.version), reverse=True)
        return entries[:limit]

    def get_entry(self, version: str) -> Optional[ChangelogEntry]:
        """Get changelog entry for a specific version string (e.g. '0.1.63' or 'v0.1.63')."""
        v = version.lstrip("v")
        path = self._dir / f"v{v}.md"
        if not path.exists():
            return None
        return self._parse_file(path)

    def get_latest(self) -> Optional[ChangelogEntry]:
        entries = self.list_entries(limit=1)
        return entries[0] if entries else None

    def write_entry(self, version: str, title: str, content: str) -> Path:
        """Write a new changelog entry. Creates directory if needed."""
        v = version.lstrip("v")
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"v{v}.md"
        today = date.today().isoformat()
        body = f"# v{v} — {title}\n\n**Date:** {today}\n\n{content.strip()}\n"
        path.write_text(body, encoding="utf-8")
        return path

    def _parse_file(self, path: Path) -> Optional[ChangelogEntry]:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return None

        header = _HEADER_RE.search(text)
        if not header:
            return None

        version = header.group(1).lstrip("v")
        title = header.group(2).strip()

        release_date: Optional[date] = None
        date_match = _DATE_RE.search(text)
        if date_match:
            try:
                release_date = date.fromisoformat(date_match.group(1))
            except ValueError:
                pass

        # content = everything after the first line
        first_newline = text.find("\n")
        content = text[first_newline:].strip() if first_newline != -1 else ""

        return ChangelogEntry(
            version=version,
            title=title,
            release_date=release_date,
            content=content,
        )
