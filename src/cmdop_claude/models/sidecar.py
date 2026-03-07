"""Sidecar models for documentation analysis."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, NonNegativeInt

from .base import CoreModel


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


# ── Structured output models (sent to LLM via response_format) ───────


class ReviewCategory(str, Enum):
    staleness = "staleness"
    contradiction = "contradiction"
    gap = "gap"
    abandoned_plan = "abandoned_plan"


class ReviewSeverity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class LLMReviewItem(BaseModel):
    """Single issue — schema for LLM structured output."""

    category: ReviewCategory
    severity: ReviewSeverity
    description: str = Field(
        min_length=1, description="Specific problem with file names and quotes"
    )
    affected_files: list[str] = Field(
        description="Paths of affected documentation files"
    )
    suggested_action: str = Field(
        min_length=1, description="A question or action for the developer"
    )


class LLMReviewResponse(BaseModel):
    """Top-level response from LLM — used as response_format in client.parse()."""

    items: list[LLMReviewItem] = Field(
        max_length=10,
        description="List of documentation issues found, max 10, ordered by severity",
    )


# ── Internal models (with computed item_id) ──────────────────────────


class ReviewItem(CoreModel):
    """A single issue found by the sidecar, with generated item_id."""

    category: ReviewCategory
    severity: ReviewSeverity
    description: str = Field(min_length=1)
    affected_files: list[str] = Field(default_factory=list)
    suggested_action: str = Field(min_length=1)
    item_id: str = Field(min_length=1)


class ReviewResult(CoreModel):
    """Full review output from the sidecar."""

    generated_at: datetime
    items: list[ReviewItem]
    tokens_used: NonNegativeInt
    model_used: str = Field(min_length=1)


# ── Fix/Init structured output models ────────────────────────────────


class LLMFixResponse(BaseModel):
    """LLM response for fixing a single documentation file."""

    content: str = Field(
        min_length=1,
        description="Complete updated file content",
    )


class LLMInitFile(BaseModel):
    """Single file in init response."""

    path: str = Field(description="File path relative to project root, e.g. CLAUDE.md or .claude/rules/testing.md")
    content: str = Field(min_length=1, description="Complete file content")


class LLMInitResponse(BaseModel):
    """LLM response for project init — generates multiple files."""

    files: list[LLMInitFile] = Field(
        description="List of files to create",
    )


class FixResult(CoreModel):
    """Result of a fix operation."""

    file_path: str
    diff: str
    applied: bool = False
    tokens_used: int = 0


class InitResult(CoreModel):
    """Result of an init operation."""

    files_created: list[str]
    tokens_used: int = 0
    model_used: str = "unknown"


class ActivityEntry(CoreModel):
    """Single activity log entry."""

    ts: datetime
    action: str
    tokens: int = 0
    model: str = ""
    details: dict = Field(default_factory=dict)


class SidecarStatus(CoreModel):
    """Current sidecar state."""

    enabled: bool
    last_run: Optional[datetime] = None
    pending_items: NonNegativeInt = 0
    suppressed_items: NonNegativeInt = 0
    tokens_today: NonNegativeInt = 0
    cost_today_usd: float = Field(default=0.0, ge=0.0)
