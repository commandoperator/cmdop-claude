"""Activity log entry model."""
from datetime import datetime

from pydantic import Field

from cmdop_claude.models.base import CoreModel


class ActivityEntry(CoreModel):
    """Single activity log entry."""

    ts: datetime
    action: str
    tokens: int = 0
    model: str = ""
    details: dict = Field(default_factory=dict)
