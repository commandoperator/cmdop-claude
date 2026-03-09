"""Hooks service."""
import json
from pathlib import Path
from typing import Dict, Optional

from cmdop_claude._config import Config
from cmdop_claude.models.claude.hooks import HookConfig
from cmdop_claude.services.base import BaseService

class HooksService(BaseService):
    """Service for managing Claude hooks."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._hooks_dir = Path(self._config.claude_dir_path) / "hooks"

    def list_hooks(self) -> Dict[str, HookConfig]:
        """List all configured hooks."""
        if not self._hooks_dir.exists():
            return {}
        hooks = {}
        for f in self._hooks_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text("utf-8"))
                # Filter out pure json files that might not match the schema strictly if needed,
                # but Pydantic will validate.
                hooks[f.stem] = HookConfig(**data)
            except Exception:
                pass
        return hooks

    def get_hook_script(self, script_path: str) -> str:
        """Get the content of the script tied to a hook."""
        path = Path(self._config.claude_dir_path) / script_path
        if path.exists() and path.is_file():
            return path.read_text("utf-8")
        return ""

    def update_hook_script(self, script_path: str, content: str) -> None:
        """Update the content of the script tied to a hook."""
        path = Path(self._config.claude_dir_path) / script_path
        if path.exists():
            path.write_text(content, encoding="utf-8")
