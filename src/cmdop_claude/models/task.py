"""Models for the sidecar task queue."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, NonNegativeInt

from .base import CoreModel


class TaskPriority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    dismissed = "dismissed"


class TaskSource(str, Enum):
    sidecar_review = "sidecar_review"
    manual = "manual"
    map_update = "map_update"


class SidecarTask(CoreModel):
    """A single task in the sidecar queue."""

    id: str = Field(min_length=1)
    priority: TaskPriority
    status: TaskStatus = "pending"  # type: ignore[assignment]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    context_files: list[str] = Field(default_factory=list)
    source: TaskSource
    source_item_id: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskQueue(CoreModel):
    """Summary of the task queue state."""

    total: NonNegativeInt = 0
    pending: NonNegativeInt = 0
    in_progress: NonNegativeInt = 0
    completed: NonNegativeInt = 0
    dismissed: NonNegativeInt = 0
