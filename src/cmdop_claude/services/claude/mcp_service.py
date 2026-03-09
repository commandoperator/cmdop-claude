"""Service for managing MCP servers and Claude settings."""
import json
import os
from pathlib import Path
from typing import Optional

from cmdop_claude._config import Config
from cmdop_claude.models.config.mcp import MCPConfig, ClaudeSettings
from cmdop_claude.services.base import BaseService

class MCPService(BaseService):
    """Service to handle Model Context Protocol and Claude settings across scopes."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._project_mcp_file = Path(".mcp.json")
        self._global_mcp_file = Path(os.path.expanduser("~/.claude.json"))

        self._project_settings_file = Path(self._config.claude_dir_path) / "settings.json"
        self._user_settings_file = Path(os.path.expanduser("~/.claude/settings.json"))
        self._local_settings_file = Path(self._config.claude_dir_path) / "settings.local.json"

    def get_project_mcp_config(self) -> MCPConfig:
        """Read .mcp.json."""
        return self._read_mcp_file(self._project_mcp_file)

    def write_project_mcp_config(self, config: MCPConfig) -> None:
        """Write to .mcp.json."""
        self._write_json_file(self._project_mcp_file, config.model_dump(exclude_none=True))

    def get_global_mcp_config(self) -> MCPConfig:
        """Read ~/.claude.json."""
        return self._read_mcp_file(self._global_mcp_file)

    def write_global_mcp_config(self, config: MCPConfig) -> None:
        """Write to ~/.claude.json."""
        self._write_json_file(self._global_mcp_file, config.model_dump(exclude_none=True))

    def get_merged_mcp_config(self) -> MCPConfig:
        """Merge project and global MCP servers."""
        global_cfg = self.get_global_mcp_config()
        project_cfg = self.get_project_mcp_config()

        merged_servers = {**global_cfg.mcpServers, **project_cfg.mcpServers}
        return MCPConfig(mcpServers=merged_servers)

    def _read_mcp_file(self, path: Path) -> MCPConfig:
        if not path.exists():
            return MCPConfig()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return MCPConfig.model_validate(data)
        except Exception:
            return MCPConfig()

    def _write_json_file(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_settings(self, scope: str = "project") -> ClaudeSettings:
        """Get settings for a specific scope (project, user, local)."""
        file_map = {
            "project": self._project_settings_file,
            "user": self._user_settings_file,
            "local": self._local_settings_file
        }
        path = file_map.get(scope)
        if not path or not path.exists():
            return ClaudeSettings()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ClaudeSettings.model_validate(data)
        except Exception:
            return ClaudeSettings()

    def write_settings(self, settings: ClaudeSettings, scope: str = "project") -> None:
        """Write settings for a specific scope."""
        file_map = {
            "project": self._project_settings_file,
            "user": self._user_settings_file,
            "local": self._local_settings_file
        }
        path = file_map.get(scope)
        if path:
            self._write_json_file(path, settings.model_dump(exclude_none=True))
