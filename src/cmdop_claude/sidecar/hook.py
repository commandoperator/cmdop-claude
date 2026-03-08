"""CLI entry point for sidecar hooks.

Usage from Claude Code hooks:
    python -m cmdop_claude.sidecar.hook scan
    python -m cmdop_claude.sidecar.hook status
    python -m cmdop_claude.sidecar.hook acknowledge <item_id> [days]
    python -m cmdop_claude.sidecar.hook map-update
    python -m cmdop_claude.sidecar.hook inject-tasks
    python -m cmdop_claude.sidecar.hook fix <task_id> [--apply]
    python -m cmdop_claude.sidecar.hook init
    python -m cmdop_claude.sidecar.hook register
    python -m cmdop_claude.sidecar.hook unregister
"""
import json
import sys
import time
from pathlib import Path

from sdkrouter._constants import HOMEPAGE_URL

from .._config import Config, get_config
from ..services.sidecar_service import SidecarService

_API_KEY_ERROR_MSG = (
    "\n  SDKROUTER_API_KEY is missing or invalid.\n"
    f"  Get your API key at: {HOMEPAGE_URL}\n"
    "  Then: export SDKROUTER_API_KEY=your-key-here\n"
)


def _is_api_key_error(e: Exception) -> bool:
    """Check if exception is an API key / credits issue."""
    msg = str(e).lower()
    return any(w in msg for w in ("401", "402", "403", "unauthorized", "insufficient", "invalid api", "api key"))

# Debounce interval for map-update (seconds)
_MAP_UPDATE_DEBOUNCE = 60
# Auto-scan interval (seconds) — review docs once per 24h
_AUTO_SCAN_INTERVAL = 86400


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m cmdop_claude.sidecar.hook "
            "<scan|status|acknowledge|map-update|inject-tasks|fix|init|register|unregister|setup|activity>"
        )
        sys.exit(1)

    command = sys.argv[1]
    config = get_config()
    sidecar = SidecarService(config)

    if command == "scan":
        try:
            result = sidecar.generate_review()
            print(f"Review generated: {len(result.items)} items found")
            print(f"Tokens used: {result.tokens_used} ({result.model_used})")
        except RuntimeError as e:
            print(f"Skipped: {e}")
        except Exception as e:
            if _is_api_key_error(e):
                print(f"Error: {e}{_API_KEY_ERROR_MSG}")
            else:
                print(f"Error: {e}")

    elif command == "status":
        status = sidecar.get_status()
        print(json.dumps(status.model_dump(), indent=2, default=str))

    elif command == "acknowledge":
        if len(sys.argv) < 3:
            print("Usage: acknowledge <item_id> [days]")
            sys.exit(1)
        item_id = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        sidecar.acknowledge(item_id, days)
        print(f"Suppressed {item_id} for {days} days")

    elif command == "map-update":
        _handle_map_update(sidecar, config)

    elif command == "inject-tasks":
        _handle_inject_tasks(sidecar)

    elif command == "fix":
        _handle_fix(sidecar)

    elif command == "init":
        _handle_init(sidecar)

    elif command in ("register", "setup"):
        mcp_added = sidecar.register_mcp()
        if mcp_added:
            print("Registered sidecar MCP server in ~/.claude.json")
        else:
            print("MCP server already registered.")
        _setup_and_init(sidecar, config)

    elif command == "unregister":
        if sidecar.unregister_mcp():
            print("Unregistered sidecar MCP server from ~/.claude.json")
        else:
            print("Not registered.")

    elif command == "activity":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        entries = sidecar.get_activity(limit=limit)
        if not entries:
            print("No activity recorded yet.")
        else:
            for e in entries:
                details = " ".join(f"{k}={v}" for k, v in e.details.items())
                print(f"[{e.ts.strftime('%Y-%m-%d %H:%M')}] {e.action} | {e.tokens} tok | {details}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


def _maybe_prompt_api_key() -> None:
    """Interactively ask for SDKROUTER_API_KEY if not set and stdin is a TTY."""
    from .._config import get_config
    from ..models.cmdop_config import CmdopConfig

    if not sys.stdin.isatty():
        return
    if get_config().sdkrouter_api_key:
        return
    print()
    print("  SDKROUTER_API_KEY is not set — LLM features won't work.")
    print("  Get your key at: https://sdkrouter.com")
    try:
        key = input("  Enter API key (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if key:
        CmdopConfig.load().set_api_key(key)
        print("  Saved to ~/.claude/cmdop.json")


def _setup_and_init(sidecar: SidecarService, config: "Config") -> None:
    """Setup project hooks and auto-init if CLAUDE.md doesn't exist."""
    _maybe_prompt_api_key()
    hooks_added = sidecar.setup_project_hooks()
    if hooks_added:
        for h in hooks_added:
            print(f"  Hook added: {h}")
    else:
        print("  Project hooks already configured.")

    # Auto-init if bare project (no CLAUDE.md)
    claude_md = Path(config.claude_dir_path).parent / "CLAUDE.md"
    if not claude_md.exists():
        print("  No CLAUDE.md found — running init...")
        _handle_init(sidecar)


def _handle_map_update(sidecar: SidecarService, config: "Config") -> None:
    """Incremental map update with debounce — skip if last run < 60s ago."""
    map_path = Path(config.claude_dir_path) / "project-map.md"
    if map_path.exists():
        age = time.time() - map_path.stat().st_mtime
        if age < _MAP_UPDATE_DEBOUNCE:
            print(f"Skipped: map updated {age:.0f}s ago (debounce {_MAP_UPDATE_DEBOUNCE}s)")
            return

    try:
        result = sidecar.generate_map()
        print(
            f"Map updated: {len(result.directories)} dirs, "
            f"{len(result.entry_points)} entry points, "
            f"{result.tokens_used} tokens ({result.model_used})"
        )
    except Exception as e:
        if _is_api_key_error(e):
            print(f"Error: {e}{_API_KEY_ERROR_MSG}")
        else:
            print(f"Error: {e}")


def _handle_inject_tasks(sidecar: SidecarService) -> None:
    """Print top pending tasks to stdout for UserPromptSubmit hook injection.

    Auto-triggers a review scan if the last one was >24h ago (or never ran).
    Review items are auto-converted to tasks.
    """
    _maybe_auto_scan(sidecar)
    summary = sidecar.get_pending_summary(max_items=3)
    if summary:
        print(summary)


def _maybe_auto_scan(sidecar: SidecarService) -> None:
    """Run review + convert to tasks if last scan was >24h ago."""
    age = sidecar.last_action_age("review")
    if age is not None and age < _AUTO_SCAN_INTERVAL:
        return
    try:
        result = sidecar.generate_review()
        if result.items:
            sidecar.convert_review_to_tasks(result.items)
    except RuntimeError:
        pass  # lock held — skip silently


def _handle_fix(sidecar: SidecarService) -> None:
    """Generate a fix for a task. Usage: fix <task_id> [--apply]"""
    if len(sys.argv) < 3:
        print("Usage: fix <task_id> [--apply]")
        sys.exit(1)
    task_id = sys.argv[2]
    apply = "--apply" in sys.argv[3:]
    try:
        result = sidecar.fix_task(task_id, apply=apply)
        if result.diff == "Task not found.":
            print(f"Task {task_id} not found.")
            sys.exit(1)
        print(result.diff)
        if result.applied:
            print(f"\nApplied to {result.file_path}. Task marked completed.")
        print(f"Tokens: {result.tokens_used}")
    except Exception as e:
        if _is_api_key_error(e):
            print(f"Error: {e}{_API_KEY_ERROR_MSG}")
        else:
            print(f"Error: {e}")
        sys.exit(1)


def _handle_init(sidecar: SidecarService) -> None:
    """Initialize .claude/ for a bare project."""
    try:
        result = sidecar.init_project()
        if not result.files_created:
            print(f"Skipped: {result.model_used}")
            return
        print(f"Initialized {len(result.files_created)} files:")
        for f in result.files_created:
            print(f"  - {f}")
        print(f"Model: {result.model_used} | Tokens: {result.tokens_used}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
