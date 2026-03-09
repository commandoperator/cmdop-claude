"""E2E test: full runtime flow without real LLM calls.

Creates a realistic test project in tmp_path, wires up the full stack,
and verifies the complete flow:
  1. Client init + config
  2. Scanner finds docs
  3. Review (mocked LLM) → review.md written
  4. Review items → tasks auto-created
  5. Task CRUD via service
  6. Project map (mocked LLM) → project-map.md written
  7. Map cache hit on second run
  8. Hook CLI: status, inject-tasks, map-update
  9. MCP tools: all 9 tools callable
 10. Suppression + prune + usage tracking
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_project(root: Path) -> Path:
    """Scaffold a realistic project structure."""
    # .claude/ docs
    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text(
        "# Project Instructions\n\nUse Python 3.10+. Pydantic v2 for models.\n",
        encoding="utf-8",
    )
    rules_dir = claude_dir / "rules"
    rules_dir.mkdir()
    (rules_dir / "testing.md").write_text(
        "# Testing Rules\n\nUse pytest. 100% coverage target.\n",
        encoding="utf-8",
    )
    skills_dir = claude_dir / "skills" / "code_reviewer"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: Code Reviewer\ndescription: Reviews PRs\n---\n# Code Reviewer\nCheck types.\n",
        encoding="utf-8",
    )

    # Source code dirs
    src = root / "src" / "myapp"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("__version__ = '1.0.0'\n")
    (src / "main.py").write_text("def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n")
    (src / "auth.py").write_text("class AuthService:\n    pass\n")

    models = src / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "user.py").write_text("from pydantic import BaseModel\n\nclass User(BaseModel):\n    name: str\n")

    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_main():\n    assert True\n")

    # Config files
    (root / "pyproject.toml").write_text('[project]\nname = "myapp"\nversion = "1.0.0"\n')
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv/\nnode_modules/\n")

    # Init git (needed for scanner)
    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=str(root),
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t.com"},
    )

    return claude_dir


def _mock_sdk_parse(response_format=None, **kwargs):
    """Return a mock SDK response that matches the expected format."""
    from cmdop_claude.models.sidecar import LLMReviewResponse

    # Check what response_format is expected
    if response_format and response_format.__name__ == "LLMReviewResponse":
        parsed = LLMReviewResponse(
            items=[
                {
                    "category": "staleness",
                    "severity": "high",
                    "description": "CLAUDE.md has not been updated in 45 days",
                    "affected_files": ["CLAUDE.md"],
                    "suggested_action": "Review and update project instructions",
                },
                {
                    "category": "gap",
                    "severity": "medium",
                    "description": "src/myapp/auth.py has no documentation coverage",
                    "affected_files": ["src/myapp/auth.py"],
                    "suggested_action": "Add auth documentation to rules",
                },
            ]
        )
    else:
        # LLMMapResponse
        from cmdop_claude.models.project_map import LLMMapResponse

        parsed = LLMMapResponse(
            project_type="python-package",
            root_summary="Python CLI application with auth and models",
            directories=[
                {"path": "src/myapp", "annotation": "Main application package with auth and models", "is_entry_point": True, "entry_file": "main.py"},
                {"path": "src/myapp/models", "annotation": "Pydantic v2 domain models", "is_entry_point": False, "entry_file": None},
                {"path": "tests", "annotation": "Pytest test suite", "is_entry_point": False, "entry_file": None},
            ],
        )

    usage = SimpleNamespace(total_tokens=150)
    message = SimpleNamespace(parsed=parsed)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage, model="mock/cheap-test")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_project(tmp_path: Path):
    """Create a test project and return (root, claude_dir)."""
    root = tmp_path / "test-project"
    root.mkdir()
    claude_dir = _create_test_project(root)
    return root, claude_dir


@pytest.fixture()
def service(test_project):
    """Create a SidecarService pointed at the test project with mocked SDK."""
    root, claude_dir = test_project

    from cmdop_claude._config import Config
    from cmdop_claude.services.sidecar import SidecarService

    config = Config(
        claude_dir_path=str(claude_dir),
        sdkrouter_api_key="test-key",
    )
    svc = SidecarService(config)

    # Mock the SDK
    mock_sdk = MagicMock()
    mock_sdk.parse.side_effect = _mock_sdk_parse
    svc._sdk = mock_sdk

    return svc, root, claude_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProjectSetup:
    """Verify the test project is correctly scaffolded."""

    def test_claude_dir_exists(self, test_project) -> None:
        root, claude_dir = test_project
        assert claude_dir.exists()
        assert (claude_dir / "CLAUDE.md").exists()
        assert (claude_dir / "rules" / "testing.md").exists()

    def test_source_dirs_exist(self, test_project) -> None:
        root, _ = test_project
        assert (root / "src" / "myapp" / "main.py").exists()
        assert (root / "src" / "myapp" / "models" / "user.py").exists()

    def test_git_initialized(self, test_project) -> None:
        root, _ = test_project
        assert (root / ".git").exists()


class TestScannerFlow:
    """Test the doc scanner finds files correctly."""

    def test_scan_finds_docs(self, service) -> None:
        svc, root, claude_dir = service
        result = svc.scan()

        assert len(result.files) > 0
        paths = [f.path for f in result.files]
        assert any("CLAUDE.md" in p for p in paths)
        assert any("testing.md" in p for p in paths)

    def test_scan_finds_dirs(self, service) -> None:
        svc, root, claude_dir = service
        result = svc.scan()
        assert len(result.top_dirs) > 0


class TestReviewFlow:
    """Test the full review pipeline."""

    def test_generate_review(self, service) -> None:
        svc, root, claude_dir = service
        result = svc.generate_review()

        assert len(result.items) == 2
        assert result.items[0].category == "staleness"
        assert result.items[1].category == "gap"
        assert result.tokens_used == 150
        assert result.model_used == "mock/cheap-test"

    def test_review_md_written(self, service) -> None:
        svc, root, claude_dir = service
        svc.generate_review()

        review_path = claude_dir / ".sidecar" / "review.md"
        assert review_path.exists()
        content = review_path.read_text(encoding="utf-8")
        assert "Staleness" in content
        assert "CLAUDE.md" in content

    def test_history_archived(self, service) -> None:
        svc, root, claude_dir = service
        svc.generate_review()

        history_dir = claude_dir / ".sidecar" / "history"
        assert history_dir.exists()
        history_files = list(history_dir.glob("*.md"))
        assert len(history_files) == 1

    def test_usage_tracked(self, service) -> None:
        svc, root, claude_dir = service
        svc.generate_review()

        usage_file = claude_dir / ".sidecar" / "usage.json"
        assert usage_file.exists()
        data = json.loads(usage_file.read_text(encoding="utf-8"))
        assert data["tokens"] == 150
        assert data["calls"] == 1

    def test_second_review_increments_usage(self, service) -> None:
        svc, root, claude_dir = service
        svc.generate_review()
        svc.generate_review()

        usage_file = claude_dir / ".sidecar" / "usage.json"
        data = json.loads(usage_file.read_text(encoding="utf-8"))
        assert data["tokens"] == 300
        assert data["calls"] == 2

    def test_lock_prevents_concurrent(self, service) -> None:
        svc, root, claude_dir = service
        # Manually create a fresh lock
        sidecar_dir = claude_dir / ".sidecar"
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        lock = sidecar_dir / ".lock"
        lock.write_text("99999", encoding="utf-8")

        with pytest.raises(RuntimeError, match="lock"):
            svc.generate_review()

        lock.unlink()


class TestSuppressionFlow:
    """Test item suppression."""

    def test_acknowledge_suppresses_item(self, service) -> None:
        svc, root, claude_dir = service
        result1 = svc.generate_review()
        item_id = result1.items[0].item_id

        svc.acknowledge(item_id, days=30)

        result2 = svc.generate_review()
        ids = [i.item_id for i in result2.items]
        assert item_id not in ids

    def test_suppressed_json_written(self, service) -> None:
        svc, root, claude_dir = service
        svc.generate_review()
        svc.acknowledge("test-id", days=7)

        supp_file = claude_dir / ".sidecar" / "suppressed.json"
        assert supp_file.exists()
        data = json.loads(supp_file.read_text(encoding="utf-8"))
        assert "test-id" in data


class TestReviewToTasksFlow:
    """Test converting review items to tasks."""

    def test_convert_creates_tasks(self, service) -> None:
        svc, root, claude_dir = service
        result = svc.generate_review()

        created = svc.convert_review_to_tasks(result.items)
        assert len(created) == 2

        tasks_dir = claude_dir / ".sidecar" / "tasks"
        assert tasks_dir.exists()
        task_files = list(tasks_dir.glob("*.md"))
        assert len(task_files) == 2

    def test_duplicate_conversion_skipped(self, service) -> None:
        svc, root, claude_dir = service
        result = svc.generate_review()

        created1 = svc.convert_review_to_tasks(result.items)
        created2 = svc.convert_review_to_tasks(result.items)

        assert len(created1) == 2
        assert len(created2) == 0
        assert len(svc.list_tasks()) == 2

    def test_task_has_correct_metadata(self, service) -> None:
        svc, root, claude_dir = service
        result = svc.generate_review()
        created = svc.convert_review_to_tasks(result.items)

        task = created[0]
        assert task.priority == "high"
        assert task.source == "sidecar_review"
        assert task.source_item_id is not None
        assert task.status == "pending"


class TestTaskCRUD:
    """Test task create/read/update via service."""

    def test_create_manual_task(self, service) -> None:
        svc, root, claude_dir = service
        task = svc.create_task(
            title="Fix auth docs",
            description="OAuth2 added but docs say JWT",
            priority="high",
            context_files=["src/myapp/auth.py"],
        )
        assert task.id == "T-001"
        assert task.source == "manual"
        assert task.context_files == ["src/myapp/auth.py"]

    def test_list_tasks_filter(self, service) -> None:
        svc, root, claude_dir = service
        svc.create_task(title="Task A", description="desc", priority="high")
        svc.create_task(title="Task B", description="desc", priority="low")

        all_tasks = svc.list_tasks()
        assert len(all_tasks) == 2

        pending = svc.list_tasks(status="pending")
        assert len(pending) == 2

    def test_update_task_status(self, service) -> None:
        svc, root, claude_dir = service
        svc.create_task(title="Task A", description="desc")

        assert svc.update_task_status("T-001", "in_progress")
        tasks = svc.list_tasks(status="in_progress")
        assert len(tasks) == 1

        assert svc.update_task_status("T-001", "completed")
        tasks = svc.list_tasks(status="completed")
        assert len(tasks) == 1
        assert tasks[0].completed_at is not None

    def test_update_nonexistent_returns_false(self, service) -> None:
        svc, root, claude_dir = service
        assert svc.update_task_status("T-999", "completed") is False

    def test_pending_summary(self, service) -> None:
        svc, root, claude_dir = service
        svc.create_task(title="High task", description="d", priority="high")
        svc.create_task(title="Low task", description="d", priority="low")
        svc.create_task(title="Critical task", description="d", priority="critical")

        summary = svc.get_pending_summary(max_items=2)
        assert "3 total" in summary
        assert "[critical]" in summary
        lines = summary.splitlines()
        # Critical should be first
        assert "Critical" in lines[1]

    def test_pending_summary_empty(self, service) -> None:
        svc, root, claude_dir = service
        assert svc.get_pending_summary() == ""


class TestProjectMapFlow:
    """Test project map generation."""

    def test_generate_map(self, service) -> None:
        svc, root, claude_dir = service

        # Also mock the mapper's SDK
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        result = svc.generate_map()

        assert result.project_type == "python-package"
        assert len(result.directories) > 0
        assert result.tokens_used == 150

    def test_map_md_written(self, service) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        svc.generate_map()

        map_path = root / ".claude" / "project-map.md"
        assert map_path.exists()
        content = map_path.read_text(encoding="utf-8")
        assert "Project Map" in content
        assert "python-package" in content

    def test_cache_hit_on_second_run(self, service) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        result1 = svc.generate_map()
        assert result1.tokens_used == 150

        # Second run should hit cache
        result2 = svc.generate_map()
        assert result2.model_used == "cache"
        assert result2.tokens_used == 0

    def test_cache_json_created(self, service) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        svc.generate_map()

        cache_path = claude_dir / ".sidecar" / "map_cache.json"
        assert cache_path.exists()
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert len(data) > 0

    def test_get_current_map_empty(self, service) -> None:
        svc, root, claude_dir = service
        assert svc.get_current_map() == ""

    def test_get_current_map_after_generate(self, service) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        svc.generate_map()
        content = svc.get_current_map()
        assert "Project Map" in content


class TestExclusionsInMapper:
    """Test that exclusions work in the mapper context."""

    def test_junk_dirs_excluded(self, test_project) -> None:
        root, claude_dir = test_project
        # Create junk dirs
        (root / "node_modules" / "express").mkdir(parents=True)
        (root / "node_modules" / "express" / "index.js").write_text("module.exports = {}")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "main.cpython-310.pyc").write_text("bytecode")
        (root / ".venv" / "lib").mkdir(parents=True)

        from cmdop_claude.sidecar.utils.exclusions import scan_project_dirs

        dirs = scan_project_dirs(root, max_depth=3, max_dirs=50)
        dir_paths = [d.path for d in dirs]

        assert "node_modules" not in dir_paths
        assert "__pycache__" not in dir_paths
        assert ".venv" not in dir_paths

    def test_sensitive_files_not_in_snippets(self, test_project) -> None:
        root, claude_dir = test_project
        (root / ".env").write_text("SECRET_KEY=super_secret_123\nDB_URL=postgres://...\n")
        (root / "credentials.json").write_text('{"api_key": "sk-12345"}')

        from cmdop_claude.sidecar.utils.exclusions import is_sensitive_file

        assert is_sensitive_file(".env")
        assert is_sensitive_file("credentials.json")


class TestStatusFlow:
    """Test status reporting."""

    def test_status_before_any_run(self, service) -> None:
        svc, root, claude_dir = service
        status = svc.get_status()
        assert status.last_run is None
        assert status.pending_items == 0
        assert status.tokens_today == 0

    def test_status_after_review(self, service) -> None:
        svc, root, claude_dir = service
        svc.generate_review()

        status = svc.get_status()
        assert status.last_run is not None
        assert status.pending_items == 2
        assert status.tokens_today == 150


class TestMCPRegistration:
    """Test MCP server registration."""

    def test_register_and_check(self, service, monkeypatch) -> None:
        import cmdop_claude.services.sidecar.mcp_reg_service as _mcp_mod
        from types import SimpleNamespace

        svc, root, claude_dir = service
        registered = [False]

        def mock_run(cmd, **kwargs):
            if "get" in cmd:
                return SimpleNamespace(returncode=0 if registered[0] else 1, stdout="", stderr="")
            if "add" in cmd:
                registered[0] = True
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if "remove" in cmd:
                registered[0] = False
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(_mcp_mod.subprocess, "run", mock_run)

        assert svc.register_mcp() is True
        assert svc.is_mcp_registered() is True

    def test_unregister(self, service, monkeypatch) -> None:
        import cmdop_claude.services.sidecar.mcp_reg_service as _mcp_mod
        from types import SimpleNamespace

        svc, root, claude_dir = service
        registered = [True]

        def mock_run(cmd, **kwargs):
            if "get" in cmd:
                return SimpleNamespace(returncode=0 if registered[0] else 1, stdout="", stderr="")
            if "add" in cmd:
                registered[0] = True
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if "remove" in cmd:
                registered[0] = False
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(_mcp_mod.subprocess, "run", mock_run)

        assert svc.unregister_mcp() is True
        assert svc.is_mcp_registered() is False


class TestMCPTools:
    """Test all 9 MCP tools via server module functions."""

    def test_all_tools_registered(self) -> None:
        """Verify all 9 tools exist as callable functions."""
        from cmdop_claude.sidecar import server

        tool_names = [
            "sidecar_scan",
            "sidecar_review",
            "sidecar_status",
            "sidecar_acknowledge",
            "sidecar_map",
            "sidecar_map_view",
            "sidecar_tasks",
            "sidecar_task_update",
            "sidecar_task_create",
        ]
        for name in tool_names:
            assert hasattr(server, name), f"Missing MCP tool: {name}"
            assert callable(getattr(server, name))

    def test_sidecar_scan_tool(self, service) -> None:
        svc, root, claude_dir = service
        from cmdop_claude.sidecar.server import sidecar_scan

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_scan()
            assert "2 issue(s)" in result

    def test_sidecar_status_tool(self, service) -> None:
        svc, root, claude_dir = service
        from cmdop_claude.sidecar.server import sidecar_status

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_status()
            assert "Last run:" in result

    def test_sidecar_tasks_tool(self, service) -> None:
        svc, root, claude_dir = service
        svc.create_task(title="Test task", description="d")

        from cmdop_claude.sidecar.server import sidecar_tasks

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_tasks()
            assert "Test task" in result

    def test_sidecar_task_create_tool(self, service) -> None:
        svc, root, claude_dir = service
        from cmdop_claude.sidecar.server import sidecar_task_create

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_task_create(title="New", description="desc", priority="high")
            assert "T-001" in result

    def test_sidecar_task_update_tool(self, service) -> None:
        svc, root, claude_dir = service
        svc.create_task(title="T", description="d")

        from cmdop_claude.sidecar.server import sidecar_task_update

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_task_update("T-001", "completed")
            assert "updated" in result

    def test_sidecar_map_tool(self, service) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        from cmdop_claude.sidecar.server import sidecar_map

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_map()
            assert "directories" in result
            assert "python-package" in result

    def test_sidecar_map_view_tool_empty(self, service) -> None:
        svc, root, claude_dir = service
        from cmdop_claude.sidecar.server import sidecar_map_view

        with patch("cmdop_claude.sidecar.server._get_service", return_value=svc):
            result = sidecar_map_view()
            assert "No project map" in result


class TestHookCLI:
    """Test hook CLI commands via function calls."""

    def test_inject_tasks(self, service, capsys) -> None:
        svc, root, claude_dir = service
        svc.create_task(title="Pending task", description="d", priority="high")

        from cmdop_claude.sidecar.hook import _handle_inject_tasks

        _handle_inject_tasks(svc)
        captured = capsys.readouterr()
        assert "Pending task" in captured.out

    def test_inject_tasks_empty(self, service, capsys) -> None:
        svc, root, claude_dir = service
        # Log a recent review so auto-scan doesn't trigger
        svc._log_activity("review", tokens=0, model="test")

        from cmdop_claude.sidecar.hook import _handle_inject_tasks

        _handle_inject_tasks(svc)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_map_update_generates(self, service, capsys) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        from cmdop_claude._config import Config
        from cmdop_claude.sidecar.hook import _handle_map_update

        config = Config(claude_dir_path=str(claude_dir))
        _handle_map_update(svc, config)

        captured = capsys.readouterr()
        assert "Map updated" in captured.out

    def test_map_update_debounce(self, service, capsys) -> None:
        svc, root, claude_dir = service
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk

        from cmdop_claude._config import Config
        from cmdop_claude.sidecar.hook import _handle_map_update

        config = Config(claude_dir_path=str(claude_dir))

        # First run generates
        _handle_map_update(svc, config)
        captured1 = capsys.readouterr()
        assert "Map updated" in captured1.out

        # Second run should be debounced
        _handle_map_update(svc, config)
        captured2 = capsys.readouterr()
        assert "Skipped" in captured2.out


class TestFullPipeline:
    """End-to-end: scan → review → tasks → status → inject."""

    def test_complete_flow(self, service, capsys) -> None:
        svc, root, claude_dir = service

        # 1. Scan docs
        scan_result = svc.scan()
        assert len(scan_result.files) > 0

        # 2. Generate review
        review = svc.generate_review()
        assert len(review.items) == 2

        # 3. Convert to tasks
        tasks = svc.convert_review_to_tasks(review.items)
        assert len(tasks) == 2

        # 4. Check status
        status = svc.get_status()
        assert status.pending_items == 2
        assert status.tokens_today == 150

        # 5. Inject tasks
        from cmdop_claude.sidecar.hook import _handle_inject_tasks

        _handle_inject_tasks(svc)
        captured = capsys.readouterr()
        assert "2 total" in captured.out

        # 6. Complete one task
        svc.update_task_status(tasks[0].id, "completed")
        pending = svc.list_tasks(status="pending")
        assert len(pending) == 1

        # 7. Create manual task
        manual = svc.create_task(
            title="Manual task",
            description="Added by developer",
            priority="critical",
            context_files=["README.md"],
        )
        assert manual.source == "manual"

        # 8. Generate map
        mapper = svc._get_mapper()
        mapper._sdk = svc._sdk
        project_map = svc.generate_map()
        assert project_map.project_type == "python-package"

        # 9. Verify all files exist
        assert (claude_dir / ".sidecar" / "review.md").exists()
        assert (claude_dir / ".sidecar" / "usage.json").exists()
        assert (claude_dir / ".sidecar" / "tasks").exists()
        assert (root / ".claude" / "project-map.md").exists()

        task_files = list((claude_dir / ".sidecar" / "tasks").glob("*.md"))
        assert len(task_files) == 3  # 2 from review + 1 manual

        # 10. Final status
        status = svc.get_status()
        assert status.tokens_today == 300  # review + map
