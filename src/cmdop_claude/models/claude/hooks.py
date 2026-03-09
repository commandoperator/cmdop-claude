"""Hooks models."""
from typing import List, Optional
from pydantic import Field
from cmdop_claude.models.base import CoreModel

class HookConfig(CoreModel):
    """Configuration for a Claude hook."""
    events: List[str]
    script: str
    args: Optional[List[str]] = Field(default_factory=list)
