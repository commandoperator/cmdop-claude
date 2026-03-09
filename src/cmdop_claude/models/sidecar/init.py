"""Init result models."""
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from cmdop_claude.models.base import CoreModel


class DirRole(str, Enum):
    own = "own"
    external = "external"
    vendor = "vendor"


class LLMDirSummary(BaseModel):
    """Summary of a single directory — structured output from pre-summarizer."""

    path: str = Field(description="Directory path relative to project root")
    role: DirRole = Field(description="own=project code, external=vendored/archived, vendor=dependencies")
    tech_stack: list[str] = Field(default_factory=list, description="Detected technologies")
    key_files: list[str] = Field(default_factory=list, description="Important files: entry points, configs")
    commands: list[str] = Field(default_factory=list, description="Detected make targets or run scripts")

    @field_validator("tech_stack", "key_files", "commands", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: object) -> list:
        return v if isinstance(v, list) else []


class LLMTreeChunkResponse(BaseModel):
    """LLM response for a chunk of directories."""

    dirs: list[LLMDirSummary]
    project_type: str = Field(default="unknown", description="monorepo | single-app | library | unknown")


class LLMFileSelectResponse(BaseModel):
    """Step 1 of init — LLM selects which files to read."""

    files: list[str] = Field(
        description="Relative paths of files to read",
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


class InitResult(CoreModel):
    """Result of an init operation."""

    files_created: list[str]
    tokens_used: int = 0
    model_used: str = "unknown"
