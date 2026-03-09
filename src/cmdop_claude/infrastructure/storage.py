"""JSONStorage — read/write JSON files with optional Pydantic model validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Generic, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JSONStorage(Generic[T]):
    """Read/write a single JSON file. Supports both Pydantic models and raw dicts."""

    def __init__(self, path: Path, model: Optional[Type[T]] = None) -> None:
        self._path = path
        self._model = model

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> Optional[T]:
        """Load and validate as Pydantic model. Returns None on missing/invalid file."""
        assert self._model is not None, "model required for load()"
        if not self._path.exists():
            return None
        try:
            return self._model.model_validate_json(self._path.read_text("utf-8"))
        except Exception:
            return None

    def save(self, value: T) -> None:
        """Write Pydantic model as JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(value.model_dump_json(indent=2), encoding="utf-8")

    def load_dict(self) -> dict:
        """Load raw dict. Returns {} on missing/invalid file."""
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_dict(self, data: dict) -> None:
        """Write raw dict as JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
