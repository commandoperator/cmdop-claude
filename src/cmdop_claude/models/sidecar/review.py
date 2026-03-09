"""Review result models."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, NonNegativeInt

from cmdop_claude.models.base import CoreModel


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
