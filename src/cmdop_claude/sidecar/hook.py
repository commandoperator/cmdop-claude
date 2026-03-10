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

from cmdop_claude._config import Config, get_config
from cmdop_claude.services.sidecar import SidecarService

_API_KEY_ERROR_MSG = (
    "\n  API key is missing or invalid.\n"
    "  Configure it in the dashboard: make run → Settings & Security → LLM Provider\n"
    "  Or set env var: OPENROUTER_API_KEY / OPENAI_API_KEY / SDKROUTER_API_KEY\n"
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


def _setup_and_init(sidecar: SidecarService, config: "Config") -> None:
    """Setup project hooks and auto-init if CLAUDE.md doesn't exist."""
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

    # API key hint — direct to dashboard instead of interactive prompt
    from cmdop_claude.models.config.cmdop_config import CmdopConfig
    cfg = CmdopConfig.load()
    if not cfg.llm_routing.api_key and not get_config().sdkrouter_api_key:
        print()
        print("  ⚠  No LLM API key configured.")
        print("  Configure your provider and key in the dashboard:")
        print("    make run              # opens http://localhost:8501")
        print("    → Settings & Security → LLM Provider")
        print()
        print("  Or set an env var before running Claude Code:")
        print("    export OPENROUTER_API_KEY=sk-or-...")
        print("    export OPENAI_API_KEY=sk-...")
        print("    export SDKROUTER_API_KEY=...")


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

    # Prepend version line from changelog (zero LLM cost — file read only)
    _print_version_line()

    summary = sidecar.get_pending_summary(max_items=3)
    if summary:
        print(summary)


def _print_version_line() -> None:
    """Print a one-line version banner if a changelog entry exists for current version."""
    try:
        import importlib.metadata
        from cmdop_claude.services.changelog import ChangelogService
        current_version = importlib.metadata.version("cmdop-claude")
        config = get_config()
        changelog_dir = Path(config.claude_dir_path).parent / "changelog"
        svc = ChangelogService(changelog_dir)
        entry = svc.get_entry(current_version)
        if entry:
            date_str = entry.release_date.isoformat() if entry.release_date else ""
            date_part = f" | {date_str}" if date_str else ""
            print(f"📦 cmdop-claude v{entry.version}{date_part} | {entry.title}")
    except Exception:
        pass


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
