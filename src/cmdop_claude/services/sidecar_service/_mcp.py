"""Sidecar MCP registration in ~/.claude.json (global)."""
import json
from pathlib import Path

from ._base import SidecarBase

_CMDOP_CONFIG = Path.home() / ".claude" / "cmdop.json"


def _global_claude_json() -> Path:
    """Return path to ~/.claude.json."""
    return Path.home() / ".claude.json"


def save_api_key(key: str) -> None:
    """Save SDKROUTER_API_KEY to ~/.claude/cmdop.json."""
    _CMDOP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if _CMDOP_CONFIG.exists():
        try:
            data = json.loads(_CMDOP_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["sdkrouterApiKey"] = key
    _CMDOP_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")


class MCPMixin(SidecarBase):
    """Register/unregister sidecar MCP server in global ~/.claude.json."""

    def register_mcp(self) -> bool:
        """Register the sidecar MCP server in ~/.claude.json. Returns True if added."""
        path = _global_claude_json()
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

        servers = data.get("mcpServers", {})
        if "sidecar" in servers:
            return False

        servers["sidecar"] = {
            "command": "python",
            "args": ["-m", "cmdop_claude.sidecar.server"],
        }
        data["mcpServers"] = servers
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True

    def unregister_mcp(self) -> bool:
        """Remove the sidecar MCP server from ~/.claude.json. Returns True if removed."""
        path = _global_claude_json()
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False

        servers = data.get("mcpServers", {})
        if "sidecar" not in servers:
            return False

        del servers["sidecar"]
        data["mcpServers"] = servers
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True

    def setup_project_hooks(self) -> list[str]:
        """Create .claude/settings.json with hooks in the current project.

        Returns list of what was set up. Skips if settings.json already exists.
        """
        settings_path = self._claude_dir / "settings.json"
        created: list[str] = []

        if settings_path.exists():
            # Merge hooks into existing settings
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
            self._claude_dir.mkdir(parents=True, exist_ok=True)

        hooks = data.get("hooks", {})
        changed = False

        # PostToolUse: map-update on Write|Edit
        post_hooks = hooks.get("PostToolUse", [])
        has_map = any(
            "map-update" in cmd
            for h in post_hooks if isinstance(h, dict)
            for cmd in (
                [h.get("command", "")] +
                [hh.get("command", "") for hh in h.get("hooks", []) if isinstance(hh, dict)]
            )
        )
        if not has_map:
            post_hooks.append({
                "matcher": "Write|Edit",
                "hooks": [{"type": "command", "command": "python -m cmdop_claude.sidecar.hook map-update"}],
            })
            hooks["PostToolUse"] = post_hooks
            created.append("PostToolUse → map-update")
            changed = True

        # UserPromptSubmit: inject-tasks
        user_hooks = hooks.get("UserPromptSubmit", [])
        has_inject = any(
            "inject-tasks" in cmd
            for h in user_hooks if isinstance(h, dict)
            for cmd in (
                [h.get("command", "")] +
                [hh.get("command", "") for hh in h.get("hooks", []) if isinstance(hh, dict)]
            )
        )
        if not has_inject:
            user_hooks.append({
                "matcher": "",
                "hooks": [{"type": "command", "command": "python -m cmdop_claude.sidecar.hook inject-tasks"}],
            })
            hooks["UserPromptSubmit"] = user_hooks
            created.append("UserPromptSubmit → inject-tasks")
            changed = True

        # plansDirectory: store plans in project, not ~/.claude/plans/
        if "plansDirectory" not in data:
            data["plansDirectory"] = ".claude/plans"
            created.append("plansDirectory → .claude/plans")
            changed = True

        if changed:
            data["hooks"] = hooks
            settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Create plans directory
        plans_dir = self._claude_dir / "plans"
        if not plans_dir.exists():
            plans_dir.mkdir(parents=True, exist_ok=True)

        # Generate Makefile with convenience commands
        created.extend(self._generate_makefile())

        return created

    def is_mcp_registered(self) -> bool:
        """Check if the sidecar MCP server is in ~/.claude.json."""
        path = _global_claude_json()
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return "sidecar" in data.get("mcpServers", {})
        except Exception:
            return False

    def _generate_makefile(self) -> list[str]:
        """Create .claude/Makefile with convenience commands if it doesn't exist.

        Returns list of created items. Skips if Makefile already exists.
        """
        makefile_path = self._claude_dir / "Makefile"
        if makefile_path.exists():
            return []

        self._claude_dir.mkdir(parents=True, exist_ok=True)

        # Resolve the Python that has cmdop_claude installed
        import sys
        python_path = sys.executable

        content = f"""\
.PHONY: dashboard scan map activity status init

# Auto-detected Python with cmdop_claude installed
PYTHON := {python_path}

# ── cmdop-claude convenience commands ────────────────────────────────

dashboard:
\t$(PYTHON) -m streamlit run $$($(PYTHON) -c "from pathlib import Path; import cmdop_claude.ui; print(Path(cmdop_claude.ui.__file__).parent / 'main.py')")

scan:
\t$(PYTHON) -m cmdop_claude.sidecar.hook review

map:
\t$(PYTHON) -m cmdop_claude.sidecar.hook map-update

activity:
\t$(PYTHON) -m cmdop_claude.sidecar.hook activity

status:
\t$(PYTHON) -m cmdop_claude.sidecar.hook status

init:
\t$(PYTHON) -m cmdop_claude.sidecar.hook init
"""
        makefile_path.write_text(content, encoding="utf-8")
        return ["Makefile → .claude/Makefile"]
