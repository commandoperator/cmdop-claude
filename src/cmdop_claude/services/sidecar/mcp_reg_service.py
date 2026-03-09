"""MCPRegService — register/unregister sidecar MCP server via claude CLI."""
from __future__ import annotations

import json
import subprocess
import sys

from cmdop_claude.models.cmdop_config import CmdopConfig

from .state import SidecarState


def save_api_key(key: str) -> None:
    """Save SDKROUTER_API_KEY to ~/.claude/cmdop.json via CmdopConfig."""
    CmdopConfig.load().set_api_key(key)


class MCPRegService:
    def __init__(self, state: SidecarState) -> None:
        self._s = state

    def register_mcp(self) -> bool:
        if self.is_mcp_registered():
            return False
        result = subprocess.run(
            ["claude", "mcp", "add", "sidecar", "--", sys.executable, "-m", "cmdop_claude.sidecar.server"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def unregister_mcp(self) -> bool:
        if not self.is_mcp_registered():
            return False
        result = subprocess.run(
            ["claude", "mcp", "remove", "sidecar"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def is_mcp_registered(self) -> bool:
        result = subprocess.run(
            ["claude", "mcp", "get", "sidecar"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def setup_project_hooks(self) -> list[str]:
        settings_path = self._s.claude_dir / "settings.json"
        created: list[str] = []

        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
            self._s.claude_dir.mkdir(parents=True, exist_ok=True)

        hooks = data.get("hooks", {})
        changed = False

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

        if "plansDirectory" not in data:
            data["plansDirectory"] = ".claude/plans"
            created.append("plansDirectory → .claude/plans")
            changed = True

        if changed:
            data["hooks"] = hooks
            settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        plans_dir = self._s.claude_dir / "plans"
        if not plans_dir.exists():
            plans_dir.mkdir(parents=True, exist_ok=True)

        created.extend(self._generate_makefile())
        return created

    def _generate_makefile(self) -> list[str]:
        makefile_path = self._s.claude_dir / "Makefile"
        if makefile_path.exists():
            return []

        self._s.claude_dir.mkdir(parents=True, exist_ok=True)
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
