"""Claude project level service."""
import json
from pathlib import Path
from typing import Optional

from .._config import Config
from .._constants import MAX_CONTEXT_LINES
from ..models.claude import ContextHealth
from ..models.permissions import PermissionsConfig
from .base import BaseService

class ClaudeService(BaseService):
    """Service for global Claude project files."""

    __slots__ = ("_claude_dir", "_root_claude_md", "_permissions_file")

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._claude_dir = Path(self._config.claude_dir_path)
        self._root_claude_md = Path("CLAUDE.md")
        self._permissions_file = self._claude_dir / ".permissions.json"

    def get_context_health(self, file_path: str = "CLAUDE.md") -> ContextHealth:
        """Check the health of a context file."""
        path = Path(file_path)
        if not path.exists():
            return ContextHealth(
                file_path=file_path,
                line_count=0,
                is_healthy=False,
                warning_message="File does not exist."
            )
            
        lines = path.read_text(encoding="utf-8").splitlines()
        line_count = len(lines)
        is_healthy = line_count <= MAX_CONTEXT_LINES
        
        return ContextHealth(
            file_path=file_path,
            line_count=line_count,
            is_healthy=is_healthy,
            warning_message=None if is_healthy else f"File exceeds {MAX_CONTEXT_LINES} lines limit."
        )

    def get_permissions(self) -> Optional[PermissionsConfig]:
        """Read the .permissions.json file."""
        if not self._permissions_file.exists():
            return None
            
        try:
            data = json.loads(self._permissions_file.read_text(encoding="utf-8"))
            return PermissionsConfig.model_validate(data)
        except json.JSONDecodeError:
            return None

    def write_permissions(self, config: PermissionsConfig) -> None:
        """Write to the .permissions.json file."""
        self._claude_dir.mkdir(parents=True, exist_ok=True)
        data = config.model_dump_json(indent=2)
        self._permissions_file.write_text(data, encoding="utf-8")
