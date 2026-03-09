"""Annotation cache — maps directory content hashes to LLM-generated annotations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from cmdop_claude.sidecar.utils.exclusions import DirInfo


class AnnotationCache:
    """Hash-based cache for directory annotations.

    Stores: { dir_path: { "hash": sha256, "annotation": str } }
    File: .claude/.sidecar/map_cache.json
    """

    __slots__ = ("_path", "_data")

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._data: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def get(self, dir_path: str, current_hash: str) -> Optional[str]:
        """Return cached annotation if hash matches, else None."""
        entry = self._data.get(dir_path)
        if entry and entry.get("hash") == current_hash:
            return entry.get("annotation")
        return None

    def set(self, dir_path: str, content_hash: str, annotation: str) -> None:
        """Store or update annotation for a directory."""
        self._data[dir_path] = {"hash": content_hash, "annotation": annotation}

    def save(self) -> None:
        """Write cache to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2), encoding="utf-8"
        )

    def prune(self, valid_paths: set[str]) -> int:
        """Remove entries for directories that no longer exist. Returns count removed."""
        stale = [k for k in self._data if k not in valid_paths]
        for k in stale:
            del self._data[k]
        return len(stale)

    @property
    def size(self) -> int:
        return len(self._data)


def dir_content_hash(dir_info: DirInfo) -> str:
    """Compute SHA256 hash of sorted filenames in a directory.

    Changes when files are added, removed, or renamed.
    """
    content = "\n".join(dir_info.file_names)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
