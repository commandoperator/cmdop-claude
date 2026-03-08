"""Sidecar MCP registration via `claude mcp add` CLI.

Claude Code stores MCP servers per-project in ~/.claude.json under
projects["<path>"].mcpServers. There is no truly global user-scope that
works across all projects (known Claude Code bug #16728). We use
`claude mcp add` (local scope, default) so the server is registered for
the current project and immediately visible in `claude mcp list`.
"""
import json
import subprocess
import sys

from ._base import SidecarBase
from ...models.cmdop_config import CmdopConfig


def save_api_key(key: str) -> None:
    """Save SDKROUTER_API_KEY to ~/.claude/cmdop.json via CmdopConfig."""
    CmdopConfig.load().set_api_key(key)


class MCPMixin(SidecarBase):
    """Register/unregister sidecar MCP server via claude CLI."""

    def register_mcp(self) -> bool:
        """Register the sidecar MCP server for the current project. Returns True if added."""
        if self.is_mcp_registered():
            return False

        result = subprocess.run(
            [
                "claude", "mcp", "add",
                "sidecar", "--",
                sys.executable, "-m", "cmdop_claude.sidecar.server",
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def unregister_mcp(self) -> bool:
        """Remove the sidecar MCP server for the current project. Returns True if removed."""
        if not self.is_mcp_registered():
            return False

        result = subprocess.run(
            ["claude", "mcp", "remove", "sidecar"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

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
        """Check if the sidecar MCP server is registered via claude CLI."""
        result = subprocess.run(
            ["claude", "mcp", "get", "sidecar"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

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
