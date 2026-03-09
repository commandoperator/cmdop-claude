"""Fix result models."""
from pydantic import BaseModel, Field

from cmdop_claude.models.base import CoreModel


class LLMFixResponse(BaseModel):
    """LLM response for fixing a single documentation file."""

    content: str = Field(
        min_length=1,
        description="Complete updated file content",
    )


class FixResult(CoreModel):
    """Result of a fix operation."""

    file_path: str
    diff: str
    applied: bool = False
    tokens_used: int = 0
