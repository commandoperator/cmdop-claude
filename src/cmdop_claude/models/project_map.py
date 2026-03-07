"""Models for the project map generator."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, NonNegativeInt

from .base import CoreModel


# ── Internal models ──────────────────────────────────────────────────


class DirAnnotation(CoreModel):
    """LLM-generated annotation for a single directory."""

    path: str = Field(min_length=1)
    annotation: str = Field(min_length=1)
    file_count: NonNegativeInt
    has_entry_point: bool = False
    entry_point_name: Optional[str] = None


class ProjectMap(CoreModel):
    """Full project map with metadata."""

    generated_at: datetime
    project_type: str = Field(min_length=1)
    root_annotation: str = Field(min_length=1)
    directories: list[DirAnnotation]
    entry_points: list[str] = Field(default_factory=list)
    tokens_used: NonNegativeInt
    model_used: str = Field(min_length=1)


class MapConfig(CoreModel):
    """Configuration for map generation."""

    max_depth: int = Field(default=3, ge=1, le=10)
    max_dirs: int = Field(default=50, ge=5, le=200)
    max_output_lines: int = Field(default=150, ge=50, le=500)


# ── Structured output models (sent to LLM) ──────────────────────────


class LLMDirAnnotation(BaseModel):
    """Single directory annotation — schema for LLM structured output."""

    path: str = Field(description="Relative directory path from project root")
    annotation: str = Field(
        min_length=1,
        description="1-sentence description of the directory role, e.g. 'API routing logic'",
    )
    is_entry_point: bool = Field(
        description="True if this directory contains a main/index/cmd entry file"
    )
    entry_file: Optional[str] = Field(
        default=None,
        description="Entry point filename if is_entry_point is true",
    )


class LLMMapResponse(BaseModel):
    """LLM response for project map generation."""

    project_type: str = Field(
        description="Project type, e.g. python-package, nextjs-app, go-module, monorepo"
    )
    root_summary: str = Field(
        min_length=1,
        description="1-sentence project description",
    )
    directories: list[LLMDirAnnotation] = Field(
        description="Annotated directories, ordered by importance"
    )
