"""E2E test with REAL LLM calls via SDKRouter.

No mocks — tests the full pipeline end-to-end including:
  1. Documentation scan + LLM review
  2. Project map generation with LLM annotations
  3. Review → task conversion
  4. Cache hit on second map generation
  5. Hook CLI: inject-tasks, map-update
  6. Full pipeline: scan → review → tasks → map → status
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


def _create_test_project(root: Path) -> Path:
    """Scaffold a realistic multi-language project."""
    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True)

    (claude_dir / "CLAUDE.md").write_text(
        "# Project Instructions\n\n"
        "Tech stack: Python 3.10+, Pydantic v2, FastAPI.\n"
        "Use pytest for testing. Black for formatting.\n"
        "All models must inherit from BaseModel.\n",
        encoding="utf-8",
    )

    rules = claude_dir / "rules"
    rules.mkdir()
    (rules / "security.md").write_text(
        "# Security Rules\n\n"
        "- Never store secrets in code\n"
        "- Use JWT for authentication\n"
        "- Validate all user input with Pydantic\n",
        encoding="utf-8",
    )
    (rules / "testing.md").write_text(
        "# Testing Rules\n\n"
        "- Use pytest with fixtures\n"
        "- Minimum 80% coverage\n"
        "- Mock external services\n",
        encoding="utf-8",
    )

    skills_dir = claude_dir / "skills" / "code_reviewer"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: Code Reviewer\ndescription: Reviews PRs for type safety\n---\n"
        "# Code Reviewer\n\n1. Check strict typing\n2. Verify test coverage\n",
        encoding="utf-8",
    )

    # Source code — Python
    src = root / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("__version__ = '2.0.0'\n")
    (src / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n"
        "@app.get('/')\ndef root():\n    return {'status': 'ok'}\n"
    )
    (src / "auth.py").write_text(
        "from pydantic import BaseModel\n\n"
        "class LoginRequest(BaseModel):\n    username: str\n    password: str\n\n"
        "class AuthService:\n    def login(self, req: LoginRequest) -> str:\n        return 'token'\n"
    )

    models = src / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "user.py").write_text(
        "from pydantic import BaseModel, Field\n\n"
        "class User(BaseModel):\n    id: int\n    name: str = Field(min_length=1)\n    email: str\n"
    )
    (models / "settings.py").write_text(
        "from pydantic_settings import BaseSettings\n\n"
        "class AppSettings(BaseSettings):\n    debug: bool = False\n    db_url: str = 'sqlite:///db.sqlite'\n"
    )

    api = src / "api"
    api.mkdir()
    (api / "__init__.py").write_text("")
    (api / "routes.py").write_text(
        "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n"
        "@router.get('/users')\ndef list_users():\n    return []\n"
    )

    # Tests
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_auth.py").write_text(
        "from myapp.auth import AuthService, LoginRequest\n\n"
        "def test_login():\n    svc = AuthService()\n    assert svc.login(LoginRequest(username='a', password='b'))\n"
    )
    (tests_dir / "conftest.py").write_text(
        "import pytest\n\n@pytest.fixture\ndef client():\n    return None\n"
    )

    # Config files
    (root / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "2.0.0"\n'
        'dependencies = ["fastapi", "pydantic>=2.0", "uvicorn"]\n'
    )
    (root / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.venv/\nnode_modules/\ndist/\n.env\n"
    )
    (root / "Makefile").write_text(
        "run:\n\tuvicorn myapp.main:app\n\ntest:\n\tpytest\n"
    )

    # Junk dirs (should be excluded)
    (root / "node_modules" / "something").mkdir(parents=True)
    (root / "node_modules" / "something" / "index.js").write_text("module.exports = {}")
    (root / "__pycache__").mkdir()
    (root / ".venv" / "lib").mkdir(parents=True)

    # Sensitive files (should not be sent to LLM)
    (root / ".env").write_text("SECRET_KEY=super_secret\nDB_PASSWORD=hunter2\n")

    # Init git
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(root),
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "t@t.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "t@t.com",
        },
    )

    return claude_dir


@pytest.fixture()
def real_project(tmp_path: Path):
    """Create a test project and return (service, root, claude_dir)."""
    root = tmp_path / "real-test-project"
    root.mkdir()
    claude_dir = _create_test_project(root)

    from cmdop_claude._config import Config
    from cmdop_claude.services.sidecar_service import SidecarService

    config = Config(
        claude_dir_path=str(claude_dir),
        sdkrouter_api_key="test-api-key",
    )
    svc = SidecarService(config)
    return svc, root, claude_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRealReview:
    """Test documentation review with real LLM."""

    def test_generate_review(self, real_project) -> None:
        svc, root, claude_dir = real_project
        result = svc.generate_review()

        print(f"\n--- REVIEW RESULT ---")
        print(f"Items: {len(result.items)}")
        print(f"Model: {result.model_used}")
        print(f"Tokens: {result.tokens_used}")
        for item in result.items:
            print(f"  [{item.severity}] {item.category}: {item.description}")

        # Should find at least something (LLM is non-deterministic but project has clear issues)
        assert result.tokens_used > 0
        assert result.model_used != "unknown"

        # review.md should be written
        review_path = claude_dir / ".sidecar" / "review.md"
        assert review_path.exists()
        content = review_path.read_text(encoding="utf-8")
        assert "Sidecar Review" in content
        print(f"\n--- review.md ---")
        print(content[:500])

    def test_review_to_tasks(self, real_project) -> None:
        svc, root, claude_dir = real_project
        result = svc.generate_review()

        if not result.items:
            pytest.skip("LLM found no issues (non-deterministic)")

        tasks = svc.convert_review_to_tasks(result.items)
        print(f"\n--- TASKS CREATED ---")
        for t in tasks:
            print(f"  [{t.priority}] {t.title} (source_item: {t.source_item_id})")

        assert len(tasks) == len(result.items)

        # Verify task files exist
        tasks_dir = claude_dir / ".sidecar" / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == len(tasks)


class TestRealProjectMap:
    """Test project map generation with real LLM."""

    def test_generate_map(self, real_project) -> None:
        svc, root, claude_dir = real_project
        result = svc.generate_map()

        print(f"\n--- MAP RESULT ---")
        print(f"Type: {result.project_type}")
        print(f"Root: {result.root_annotation}")
        print(f"Dirs: {len(result.directories)}")
        print(f"Entry points: {result.entry_points}")
        print(f"Model: {result.model_used}")
        print(f"Tokens: {result.tokens_used}")
        for d in result.directories:
            ep = f" [ENTRY: {d.entry_point_name}]" if d.has_entry_point else ""
            print(f"  {d.path}/ ({d.file_count} files) — {d.annotation}{ep}")

        assert result.tokens_used > 0
        assert len(result.directories) > 0
        # LLM should detect it's a Python project
        assert any(
            kw in result.project_type.lower()
            for kw in ("python", "fastapi", "package", "web", "api")
        ), f"Unexpected project_type: {result.project_type}"

        # project-map.md should be written
        map_path = root / ".claude" / "project-map.md"
        assert map_path.exists()
        content = map_path.read_text(encoding="utf-8")
        assert "Project Map" in content
        print(f"\n--- project-map.md ---")
        print(content[:800])

    def test_cache_hit_second_run(self, real_project) -> None:
        svc, root, claude_dir = real_project

        result1 = svc.generate_map()
        print(f"First run: {result1.tokens_used} tokens ({result1.model_used})")

        result2 = svc.generate_map()
        print(f"Second run: {result2.tokens_used} tokens ({result2.model_used})")

        assert result1.tokens_used > 0
        assert result2.tokens_used == 0
        assert result2.model_used == "cache"

    def test_exclusions_work(self, real_project) -> None:
        svc, root, claude_dir = real_project
        result = svc.generate_map()

        dir_paths = [d.path for d in result.directories]
        print(f"Mapped dirs: {dir_paths}")

        assert "node_modules" not in dir_paths
        assert "__pycache__" not in dir_paths
        assert ".venv" not in dir_paths
        assert ".git" not in dir_paths


class TestRealFullPipeline:
    """Complete pipeline with real LLM calls."""

    def test_full_flow(self, real_project, capsys) -> None:
        svc, root, claude_dir = real_project

        # 1. Generate review
        print("\n=== Step 1: Review ===")
        review = svc.generate_review()
        print(f"Review: {len(review.items)} items, {review.tokens_used} tokens")

        # 2. Convert to tasks
        print("\n=== Step 2: Convert to tasks ===")
        tasks = svc.convert_review_to_tasks(review.items)
        print(f"Tasks created: {len(tasks)}")

        # 3. Generate map
        print("\n=== Step 3: Generate map ===")
        project_map = svc.generate_map()
        print(f"Map: {len(project_map.directories)} dirs, {project_map.tokens_used} tokens")

        # 4. Create manual task
        print("\n=== Step 4: Manual task ===")
        manual = svc.create_task(
            title="Add OAuth2 support",
            description="Auth currently uses basic JWT. Add OAuth2 flow.",
            priority="high",
            context_files=["src/myapp/auth.py", ".claude/rules/security.md"],
        )
        print(f"Manual task: {manual.id}")

        # 5. Status check
        print("\n=== Step 5: Status ===")
        status = svc.get_status()
        print(f"Last run: {status.last_run}")
        print(f"Pending: {status.pending_items}")
        print(f"Tokens today: {status.tokens_today}")

        # 6. Inject tasks (hook)
        print("\n=== Step 6: Inject tasks ===")
        from cmdop_claude.sidecar.hook import _handle_inject_tasks

        _handle_inject_tasks(svc)
        captured = capsys.readouterr()
        print(f"Injected:\n{captured.out}")

        # 7. Complete a task
        if tasks:
            print("\n=== Step 7: Complete task ===")
            svc.update_task_status(tasks[0].id, "completed")
            print(f"Completed: {tasks[0].id}")

        # 8. Verify all files
        print("\n=== Step 8: Verify files ===")
        files_to_check = [
            claude_dir / ".sidecar" / "review.md",
            claude_dir / ".sidecar" / "usage.json",
            claude_dir / ".sidecar" / "map_cache.json",
            root / ".claude" / "project-map.md",
        ]
        for f in files_to_check:
            exists = f.exists()
            print(f"  {'OK' if exists else 'MISSING'}: {f.name}")
            assert exists, f"Missing: {f}"

        tasks_dir = claude_dir / ".sidecar" / "tasks"
        task_files = list(tasks_dir.glob("*.md"))
        expected_task_count = len(review.items) + 1  # review tasks + manual
        print(f"  Task files: {len(task_files)} (expected {expected_task_count})")
        assert len(task_files) == expected_task_count

        # 9. Final token count
        usage = json.loads(
            (claude_dir / ".sidecar" / "usage.json").read_text(encoding="utf-8")
        )
        total_tokens = usage["tokens"]
        total_calls = usage["calls"]
        print(f"\n=== TOTAL: {total_tokens} tokens, {total_calls} LLM calls ===")

        assert total_tokens > 0
        assert total_calls == 2  # review + map
