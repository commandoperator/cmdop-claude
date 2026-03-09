"""Claude project configuration models."""
from typing import Optional
from cmdop_claude.models.base import CoreModel

class ContextHealth(CoreModel):
    """Health metrics for a context file like CLAUDE.md."""
    file_path: str
    line_count: int
    is_healthy: bool
    warning_message: Optional[str] = None

class ProjectStats(CoreModel):
    """Overall project health and statistics."""
    project_name: str
    claude_md_lines: int
    skill_count: int
    total_skill_lines: int
    hook_count: int
    mcp_count: int
    health_score: float # 0.0 to 100.0
    recommendations: list[str] = []
