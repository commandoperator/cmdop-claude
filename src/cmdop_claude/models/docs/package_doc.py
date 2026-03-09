"""Models for package documentation indexer."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from cmdop_claude.models.base import CoreModel


class ExportItem(CoreModel):
    """A single exported symbol from a package."""

    name: str
    kind: Literal["component", "hook", "function", "type", "class", "constant", "other"] = "other"
    description: str
    import_path: str
    signature: str = ""


class UsageExample(CoreModel):
    """A usage example extracted from a story file."""

    title: str
    code: str
    component: str = ""


class PackageDoc(CoreModel):
    """LLM-synthesized documentation for one package."""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    package_name: str
    package_dir: str
    summary: str
    install: str
    main_exports: list[ExportItem] = []
    examples: list[UsageExample] = []
    keywords: list[str] = []
    source_fingerprint: str = ""


class PackageLLMOverview(CoreModel):
    """Phase 1 LLM output — overview + exports (no examples)."""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    summary: str
    install: str
    main_exports: list[ExportItem] = []
    keywords: list[str] = []


class PackageLLMExamples(CoreModel):
    """Phase 2 LLM output — usage examples from stories."""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    examples: list[UsageExample] = []


class PackageCacheEntry(CoreModel):
    """Persisted cache entry — one per package dir."""

    model_config = {"populate_by_name": True, "extra": "ignore"}

    package_dir: str
    fingerprint: str
    doc: PackageDoc
    indexed_at: datetime
    tokens_used: int = 0
    model_used: str = ""


class ReindexResult(CoreModel):
    """Result of a reindex() call for one PackageSource."""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    source_path: str
    total: int
    changed: list[str] = []
    unchanged: list[str] = []
    failed: list[str] = []
    tokens_used: int = 0
    model_used: str = ""

    @property
    def changed_count(self) -> int:
        return len(self.changed)
