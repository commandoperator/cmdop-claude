"""Skill models."""
from typing import Optional
from pydantic import Field, ConfigDict
from cmdop_claude.models.base import CoreModel


class SkillFrontmatter(CoreModel):
    """YAML Frontmatter configuration for a SKILL.md file.

    Follows the agentskills.io open standard:
    - name: kebab-case, no spaces, no capitals, no 'claude'/'anthropic'
    - description: max 1024 chars, no < >, must state WHAT and WHEN
    - allowed-tools: Claude Code built-in tool names
    - disable-model-invocation: true = user-invocable only (/skill-name)
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(default=None, description="Kebab-case skill name")
    description: Optional[str] = Field(default=None, description="What the skill does and when to use it (max 1024 chars)")
    allowed_tools: list[str] = Field(default_factory=list, alias="allowed-tools")
    disable_model_invocation: bool = Field(default=False, alias="disable-model-invocation")
    model: Optional[str] = Field(default=None, description="Preferred model variant")
    # Extended fields (agentskills.io)
    license: Optional[str] = Field(default=None, description="SPDX license identifier, e.g. MIT")
    compatibility: Optional[str] = Field(default=None, description="Environment requirements or target surfaces")
    metadata: Optional[dict[str, str]] = Field(default=None, description="Arbitrary key-value metadata (author, version, mcp-server, etc.)")
