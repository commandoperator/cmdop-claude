"""Skill models."""
from typing import Annotated, Optional
from pydantic import BeforeValidator, Field, ConfigDict
from cmdop_claude.models.base import CoreModel


def _coerce_tools(v: object) -> list[str]:
    """Normalize allowed-tools: accepts YAML list, bracket list, or comma-separated string.

    Handles all real-world SKILL.md variations:
      allowed-tools: Read, Grep, Glob
      allowed-tools: [Read, Grep, Glob]
      allowed-tools: Bash(git:*), Bash(gh:*), Read
      allowed-tools:
        - Read
        - Grep
    """
    if v is None:
        return []
    if isinstance(v, str):
        return [t.strip() for t in v.split(",") if t.strip()]
    if isinstance(v, list):
        return [str(t).strip() for t in v if t]
    return []


AllowedTools = Annotated[list[str], BeforeValidator(_coerce_tools)]


class SkillFrontmatter(CoreModel):
    """YAML Frontmatter configuration for a SKILL.md file.

    Follows the agentskills.io / Claude Code open standard:
    - name: kebab-case, no spaces, no capitals, no 'claude'/'anthropic'
    - description: max 1024 chars, single-line (multi-line silently breaks Claude Code discovery)
    - allowed-tools: list or comma-separated string, supports Bash(pattern) syntax
    - disable-model-invocation: true = user-invocable only (/skill-name)
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    allowed_tools: AllowedTools = Field(default_factory=list, alias="allowed-tools")
    disable_model_invocation: bool = Field(default=False, alias="disable-model-invocation")
    user_invocable: bool = Field(default=True, alias="user-invocable")
    argument_hint: Optional[str] = Field(default=None, alias="argument-hint")
    model: Optional[str] = Field(default=None)
    context: Optional[str] = Field(default=None)
    agent: Optional[str] = Field(default=None)
    # Extended fields
    license: Optional[str] = Field(default=None)
    compatibility: Optional[str] = Field(default=None)
    metadata: Optional[dict[str, object]] = Field(default=None)
