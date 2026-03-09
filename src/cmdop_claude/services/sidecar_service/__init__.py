"""Backward-compatible re-export — SidecarService now lives in services/sidecar/."""
from cmdop_claude.services.sidecar import SidecarService

__all__ = ["SidecarService"]
