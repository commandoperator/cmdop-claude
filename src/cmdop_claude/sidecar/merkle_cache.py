"""Directory-level Merkle cache — skip LLM calls when nothing changed.

Each directory gets a hash computed from its files' mtime+size (fast path).
Hash is stored alongside the LLM summary. On next run, if hash matches → return
cached summary, no LLM call. One changed file bubbles up and invalidates only
the affected directory branch.

Cache file: .claude/.sidecar/merkle_cache.json
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Bump when prompt schema or model changes to force re-summarization
CACHE_VERSION = "1"

_EXCLUDE_DIRS = frozenset({
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    "dist", "build", ".tox", ".eggs", ".sidecar",
})
_EXCLUDE_EXTS = frozenset({".pyc", ".pyo", ".pyd"})


def _hash_file(path: Path) -> str:
    """Hash file by mtime+size — fast, avoids reading content."""
    try:
        s = path.stat()
        return hashlib.sha256(
            f"{s.st_mtime_ns}:{s.st_size}".encode()
        ).hexdigest()[:16]
    except OSError:
        return "missing"


def hash_dir(path: Path) -> str:
    """Recursively compute a Merkle hash for a directory subtree."""
    h = hashlib.sha256()
    try:
        entries = sorted(path.iterdir(), key=lambda p: p.name)
    except (PermissionError, OSError):
        return "unreadable"

    for entry in entries:
        if entry.is_dir() and entry.name in _EXCLUDE_DIRS:
            continue
        if entry.is_file() and entry.suffix in _EXCLUDE_EXTS:
            continue
        h.update(entry.name.encode())
        if entry.is_dir():
            h.update(hash_dir(entry).encode())
        elif entry.is_file():
            h.update(_hash_file(entry).encode())

    return h.hexdigest()[:24]


class MerkleCache:
    """Per-directory LLM summary cache keyed on Merkle hashes."""

    def __init__(self, cache_path: Path, model_id: str) -> None:
        self._path = cache_path
        self._model_id = model_id
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def get(self, rel_path: str, current_hash: str) -> dict | None:
        """Return cached entry if hash + model + version match. None = cache miss."""
        entry = self._data.get(rel_path)
        if not entry:
            return None
        if (
            entry.get("hash") != current_hash
            or entry.get("model_id") != self._model_id
            or entry.get("cache_version") != CACHE_VERSION
        ):
            return None
        return entry

    def put(
        self,
        rel_path: str,
        current_hash: str,
        role: str,
        tech_stack: list[str],
        key_files: list[str],
        commands: list[str],
    ) -> None:
        self._data[rel_path] = {
            "hash": current_hash,
            "model_id": self._model_id,
            "cache_version": CACHE_VERSION,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            "role": role,
            "tech_stack": tech_stack,
            "key_files": key_files,
            "commands": commands,
        }

    def flush(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.debug("MerkleCache flush failed: %s", e)

    def hit_count(self) -> int:
        return sum(1 for v in self._data.values() if v.get("cache_version") == CACHE_VERSION)
