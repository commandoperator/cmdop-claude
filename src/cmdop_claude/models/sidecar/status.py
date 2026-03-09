"""Sidecar status model."""
from datetime import datetime
from typing import Optional

from pydantic import Field, NonNegativeInt

from cmdop_claude.models.base import CoreModel


class SidecarStatus(CoreModel):
    """Current sidecar state."""

    enabled: bool
    last_run: Optional[datetime] = None
    pending_items: NonNegativeInt = 0
    suppressed_items: NonNegativeInt = 0
    tokens_today: NonNegativeInt = 0
    cost_today_usd: float = Field(default=0.0, ge=0.0)
