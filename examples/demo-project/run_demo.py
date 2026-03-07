#!/usr/bin/env python3
"""Run the full sidecar demo flow on a test project.

This script:
  1. Creates a demo FastAPI project with intentional .claude/ issues
  2. Runs documentation scan → LLM review
  3. Converts review items to tasks
  4. Generates project map with LLM annotations
  5. Shows inject-tasks output
  6. Fixes a task via LLM (dry-run → apply)
  7. Initializes .claude/ on a bare project via LLM
  8. Prints final .claude/ state

Usage:
    python run_demo.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

# Ensure cmdop-claude is importable
CMDOP_CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(CMDOP_CLAUDE_ROOT / "src"))

from setup_demo import create_demo


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def run_demo() -> None:
    # Setup
    demo_root = Path(__file__).resolve().parent / "demo-todo-app"
    if demo_root.exists():
        shutil.rmtree(demo_root)

    separator("Step 0: Create demo project")
    create_demo(demo_root)

    # Change to demo dir (sidecar reads relative paths)
    os.chdir(str(demo_root))

    # Init sidecar service
    from cmdop_claude._config import Config
    from cmdop_claude.services.sidecar_service import SidecarService

    claude_dir = demo_root / ".claude"
    config = Config(claude_dir_path=str(claude_dir))
    svc = SidecarService(config)

    # ── Step 1: Scan ──────────────────────────────────────────────
    separator("Step 1: Documentation scan (no LLM)")
    scan = svc.scan()
    print(f"Files found: {len(scan.files)}")
    for f in scan.files:
        print(f"  - {f.path} ({f.line_count} lines)")
    print(f"Dependencies: {scan.dependencies}")
    print(f"Top dirs: {scan.top_dirs}")
    print(f"Recent commits: {scan.recent_commits}")

    # ── Step 2: Review ────────────────────────────────────────────
    separator("Step 2: LLM review (detects issues in .claude/)")
    review = svc.generate_review(scan)
    print(f"Items found: {len(review.items)}")
    print(f"Model: {review.model_used}")
    print(f"Tokens: {review.tokens_used}")
    for item in review.items:
        icon = {"high": "!!!", "medium": "??", "low": "~"}.get(item.severity, "?")
        print(f"  [{icon}] [{item.category}] {item.description}")
        if item.affected_files:
            print(f"       Files: {', '.join(item.affected_files)}")
        print(f"       Action: {item.suggested_action}")

    # Show review.md
    review_md = (claude_dir / ".sidecar" / "review.md").read_text(encoding="utf-8")
    print(f"\n--- review.md ---\n{review_md}")

    # ── Step 3: Convert to tasks ──────────────────────────────────
    separator("Step 3: Convert review items to tasks")
    if review.items:
        tasks = svc.convert_review_to_tasks(review.items)
        print(f"Tasks created: {len(tasks)}")
        for t in tasks:
            print(f"  [{t.priority}] {t.id}: {t.title}")
    else:
        print("No review items — skipping task creation")
        tasks = []

    # ── Step 4: Create manual task ────────────────────────────────
    separator("Step 4: Create manual task")
    manual = svc.create_task(
        title="Add OAuth2 support",
        description="Auth currently returns 501. Implement OAuth2 flow with JWT.",
        priority="high",
        context_files=["src/todo_app/api/auth.py", ".claude/rules/security.md"],
    )
    print(f"Created: {manual.id} — {manual.title}")
    print(f"  Priority: {manual.priority}")
    print(f"  Context: {manual.context_files}")

    # ── Step 5: Project map ───────────────────────────────────────
    separator("Step 5: Generate project map (LLM)")
    project_map = svc.generate_map()
    print(f"Project type: {project_map.project_type}")
    print(f"Root: {project_map.root_annotation}")
    print(f"Directories: {len(project_map.directories)}")
    print(f"Entry points: {project_map.entry_points}")
    print(f"Model: {project_map.model_used}")
    print(f"Tokens: {project_map.tokens_used}")
    for d in project_map.directories:
        ep = f" [ENTRY: {d.entry_point_name}]" if d.has_entry_point else ""
        print(f"  {d.path}/ ({d.file_count} files) — {d.annotation}{ep}")

    # Show project-map.md
    map_md = (claude_dir / "project-map.md").read_text(encoding="utf-8")
    print(f"\n--- project-map.md ---\n{map_md}")

    # ── Step 6: Inject tasks ──────────────────────────────────────
    separator("Step 6: Inject tasks (what Claude sees)")
    summary = svc.get_pending_summary(max_items=5)
    if summary:
        print(summary)
    else:
        print("(no pending tasks)")

    # ── Step 7: Fix task (dry-run) ────────────────────────────────
    separator("Step 7: Fix task — dry run (LLM generates fix)")
    # Find the Flask→FastAPI contradiction task from review, or create one
    fix_task = None
    for t in tasks:
        if "Flask" in t.title or "flask" in t.title.lower():
            fix_task = t
            break
    if not fix_task and tasks:
        fix_task = tasks[0]
    if not fix_task:
        # Review returned 0 items (LLM parsing issue) — create task manually
        fix_task = svc.create_task(
            title="Fix Flask reference in CLAUDE.md",
            description="CLAUDE.md says 'Flask for REST API' but dependencies list 'fastapi'. Fix the framework reference.",
            priority="high",
            context_files=["CLAUDE.md"],
        )
        print(f"(created manual fix task: {fix_task.id})")

    print(f"Fixing: {fix_task.id} — {fix_task.title[:80]}")
    print(f"Target: {fix_task.context_files}")
    fix_result = svc.fix_task(fix_task.id, apply=False)
    print(f"Tokens: {fix_result.tokens_used}")
    print(f"Applied: {fix_result.applied}")
    print(f"\n--- diff (dry run) ---\n{fix_result.diff}")

    # ── Step 8: Fix task (apply) ───────────────────────────────────
    separator("Step 8: Fix task — apply")
    if fix_result.diff not in ("(no changes needed)", "Task not found.", "LLM returned no content."):
        fix_applied = svc.fix_task(fix_task.id, apply=True)
        print(f"Applied: {fix_applied.applied}")
        print(f"Task {fix_task.id} status: completed")
        target_path = demo_root / fix_applied.file_path
        if target_path.exists():
            print(f"\n--- {fix_applied.file_path} (after fix) ---")
            print(target_path.read_text(encoding="utf-8"))
    else:
        print("Skipped (no diff to apply)")

    # ── Step 9: Init on bare project ──────────────────────────────
    separator("Step 9: Init .claude/ on a bare project (LLM)")
    bare_root = Path(__file__).resolve().parent / "bare-project"
    if bare_root.exists():
        shutil.rmtree(bare_root)
    bare_root.mkdir()

    # Create a minimal project with no .claude/
    (bare_root / "pyproject.toml").write_text(
        '[project]\nname = "my-cli"\nversion = "0.1.0"\n'
        'dependencies = ["click>=8.0", "rich>=13.0", "httpx>=0.27"]\n',
        encoding="utf-8",
    )
    bare_src = bare_root / "src" / "my_cli"
    bare_src.mkdir(parents=True)
    (bare_src / "__init__.py").write_text("")
    (bare_src / "main.py").write_text(
        "import click\n\n@click.group()\ndef cli(): pass\n\n"
        "@cli.command()\ndef run():\n    click.echo('Hello')\n\n"
        "if __name__ == '__main__':\n    cli()\n",
        encoding="utf-8",
    )
    (bare_src / "api.py").write_text(
        "import httpx\n\ndef fetch(url: str) -> dict:\n"
        "    return httpx.get(url).json()\n",
        encoding="utf-8",
    )
    import subprocess as sp
    sp.run(["git", "init"], cwd=str(bare_root), capture_output=True)
    sp.run(["git", "add", "."], cwd=str(bare_root), capture_output=True)
    sp.run(
        ["git", "commit", "-m", "init: click CLI with httpx"],
        cwd=str(bare_root), capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "d@e.com",
             "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": "d@e.com"},
    )

    bare_claude_dir = bare_root / ".claude"
    bare_claude_dir.mkdir()
    bare_config = Config(claude_dir_path=str(bare_claude_dir))
    bare_svc = SidecarService(bare_config)

    print(f"Bare project: {bare_root}")
    print(f"CLAUDE.md exists: {(bare_root / 'CLAUDE.md').exists()}")

    init_result = bare_svc.init_project()
    print(f"\nFiles created: {init_result.files_created}")
    print(f"Model: {init_result.model_used}")
    print(f"Tokens: {init_result.tokens_used}")

    for fpath in init_result.files_created:
        full = bare_root / fpath
        if full.exists():
            print(f"\n--- {fpath} ---")
            print(full.read_text(encoding="utf-8"))

    # Verify init is idempotent
    init_again = bare_svc.init_project()
    print(f"\nSecond init (should skip): files={init_again.files_created}, reason={init_again.model_used}")

    # ── Step 10: Status ───────────────────────────────────────────
    separator("Step 10: Final status")
    os.chdir(str(demo_root))  # back to demo project
    status = svc.get_status()
    print(json.dumps(status.model_dump(), indent=2, default=str))

    # ── Step 11: Show .claude/ tree ───────────────────────────────
    separator("Step 11: Final .claude/ state")
    for p in sorted(claude_dir.rglob("*")):
        rel = p.relative_to(claude_dir)
        if p.is_dir():
            print(f"  {rel}/")
        else:
            size = p.stat().st_size
            print(f"  {rel}  ({size} bytes)")

    # ── Summary ───────────────────────────────────────────────────
    separator("DEMO COMPLETE")
    usage = json.loads((claude_dir / ".sidecar" / "usage.json").read_text())
    print(f"Total tokens (demo project): {usage['tokens']}")
    print(f"Total LLM calls (demo project): {usage['calls']}")
    print(f"Review items: {len(review.items)}")
    print(f"Tasks: {len(tasks) + 1} ({len(tasks)} from review + 1 manual)")
    print(f"Mapped dirs: {len(project_map.directories)}")
    print(f"Entry points: {len(project_map.entry_points)}")
    if fix_task:
        print(f"Fix applied: {fix_task.id} ({fix_result.file_path})")
    print(f"Init files: {init_result.files_created}")
    print()
    print(f"Demo project: {demo_root}")
    print(f"Bare project: {bare_root}")
    print(f"Inspect files:")
    print(f"  cat {claude_dir / '.sidecar' / 'review.md'}")
    print(f"  cat {claude_dir / 'project-map.md'}")
    print(f"  ls  {claude_dir / '.sidecar' / 'tasks'}/")


if __name__ == "__main__":
    run_demo()
