"""Shared SidecarService singleton for all tool modules."""
from __future__ import annotations

from cmdop_claude._config import get_config
from cmdop_claude.services.sidecar import SidecarService

_service: SidecarService | None = None


def get_service() -> SidecarService:
    global _service
    if _service is None:
        _service = SidecarService(get_config())
    return _service


def reset_service() -> None:
    """Reset singleton — used in tests."""
    global _service
    _service = None
