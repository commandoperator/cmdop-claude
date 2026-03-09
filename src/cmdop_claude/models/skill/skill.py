"""Skill models."""
from typing import Optional
from pydantic import Field, ConfigDict
from cmdop_claude.models.base import CoreModel

class SkillFrontmatter(CoreModel):
    """YAML Frontmatter configuration for a SKILL.md file."""
    
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(default=None, description="Name of the skill")
    description: Optional[str] = Field(default=None, description="Description of when to use the skill")
    allowed_tools: list[str] = Field(default_factory=list, alias="allowed-tools")
    disable_model_invocation: bool = Field(default=False, alias="disable-model-invocation")
    model: Optional[str] = Field(default=None, description="Preferred model variant")
