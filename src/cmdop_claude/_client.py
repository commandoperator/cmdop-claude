from pathlib import Path
from typing import Optional

from cmdop_claude._config import Config, configure, get_config
from cmdop_claude.models.claude import ProjectStats
from cmdop_claude.services.claude_service import ClaudeService
from cmdop_claude.services.hooks_service import HooksService
from cmdop_claude.services.mcp_service import MCPService
from cmdop_claude.services.plugin_service import PluginService
from cmdop_claude.services.sidecar import SidecarService, TaskService, ReviewService
from cmdop_claude.services.skill_service import SkillService


class Client:
    """Main synchronous client for the Claude Control Plane."""

    __slots__ = ("_config", "_skill_service", "_claude_service", "_hooks_service", "_mcp_service", "_plugin_service", "_sidecar_service")

    def __init__(self, claude_dir_path: Optional[str] = None) -> None:
        if claude_dir_path is not None:
            self._config = configure(claude_dir_path=claude_dir_path)
        else:
            self._config = get_config()

        self._skill_service: Optional[SkillService] = None
        self._claude_service: Optional[ClaudeService] = None
        self._hooks_service: Optional[HooksService] = None
        self._mcp_service: Optional[MCPService] = None
        self._plugin_service: Optional[PluginService] = None
        self._sidecar_service: Optional[SidecarService] = None

    @property
    def config(self) -> Config:
        return self._config

    @property
    def skills(self) -> SkillService:
        if self._skill_service is None:
            self._skill_service = SkillService(self._config)
        return self._skill_service

    @property
    def claude(self) -> ClaudeService:
        if self._claude_service is None:
            self._claude_service = ClaudeService(self._config)
        return self._claude_service

    @property
    def hooks(self) -> HooksService:
        if self._hooks_service is None:
            self._hooks_service = HooksService(self._config)
        return self._hooks_service

    @property
    def mcp(self) -> MCPService:
        if self._mcp_service is None:
            self._mcp_service = MCPService(self._config)
        return self._mcp_service

    @property
    def plugins(self) -> PluginService:
        if self._plugin_service is None:
            self._plugin_service = PluginService(self._config)
        return self._plugin_service

    @property
    def sidecar(self) -> SidecarService:
        if self._sidecar_service is None:
            self._sidecar_service = SidecarService(self._config)
        return self._sidecar_service

    @property
    def review(self) -> ReviewService:
        return self.sidecar._review

    @property
    def tasks(self) -> TaskService:
        return self.sidecar._tasks

    def get_project_dashboard_stats(self) -> ProjectStats:
        """Aggregate stats from all services for the dashboard."""
        claude_health = self.claude.get_context_health()
        skills = self.skills.list_skills()
        hooks = self.hooks.list_hooks()
        
        total_skill_lines = 0
        for name in skills:
            content = self.skills.get_skill_content(name)
            total_skill_lines += len(content.splitlines())
            
        # Basic Health Score calculation
        # 100 base. Deduct for over-sized CLAUDE.md. 
        # Bonus for having skills.
        score = 100.0
        if claude_health.line_count > 50:
            score -= (claude_health.line_count - 50) * 0.5
            
        score += min(len(skills) * 5, 20) # Max 20 bonus for skills
        score = max(0.0, min(100.0, float(score)))
        
        recommendations = []
        if claude_health.line_count > 40:
             recommendations.append("CLAUDE.md is getting long. Consider moving specialized logic to modular Skills.")
        if not skills:
             recommendations.append("No skills defined. Use 'Skill Studio' to add independent reusable capabilities.")
        if not hooks:
             recommendations.append("No automation hooks found. Consider adding post-execution or safety hooks.")

        return ProjectStats(
            project_name=Path(".").absolute().name,
            claude_md_lines=claude_health.line_count,
            skill_count=len(skills),
            total_skill_lines=total_skill_lines,
            hook_count=len(hooks),
            mcp_count=len(self.mcp.get_project_mcp_config().mcpServers) + len(self.mcp.get_global_mcp_config().mcpServers),
            health_score=score,
            recommendations=recommendations
        )
