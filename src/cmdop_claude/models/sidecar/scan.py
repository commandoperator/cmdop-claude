"""Scan result models."""
from datetime import datetime
from typing import Optional

from pydantic import NonNegativeInt

from cmdop_claude.models.base import CoreModel


class DocFile(CoreModel):
    """Metadata about a single documentation file."""

    path: str
    modified_at: datetime
    line_count: NonNegativeInt
    summary: Optional[str] = None


class DocScanResult(CoreModel):
    """Result of scanning the project documentation."""

    files: list[DocFile]
    dependencies: list[str]
    recent_commits: list[str]
    top_dirs: list[str]
