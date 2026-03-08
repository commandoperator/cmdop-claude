"""Tests for SidecarService — mock SDKRouter, test all service logic."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.sidecar import (
    DocFile,
    DocScanResult,
    FixResult,
    InitResult,
    LLMFileSelectResponse,
    LLMFixResponse,
    LLMInitFile,
    LLMInitResponse,
    LLMReviewItem,
    LLMReviewResponse,
    ReviewCategory,
    ReviewItem,
    ReviewSeverity,
)


# We need to mock SDKRouter before importing SidecarService
# because it's imported at module level


@pytest.fixture()
def mock_sdk():
    """Mock SDKRouter so no real API calls are made."""
    with patch("cmdop_claude.services.sidecar_service._base.SDKRouter") as mock_cls:
        sdk_instance = MagicMock()
        mock_cls.return_value = sdk_instance
        yield sdk_instance


@pytest.fixture()
def service(tmp_path: Path, mock_sdk):
    """Create a SidecarService with a temp .claude dir."""
    from cmdop_claude._config import Config

    from cmdop_claude.services.sidecar_service import SidecarService

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    config = Config(claude_dir_path=str(claude_dir))
    svc = SidecarService(config)
    return svc


@pytest.fixture()
def sample_scan() -> DocScanResult:
    return DocScanResult(
        files=[
            DocFile(
                path="CLAUDE.md",
                modified_at="2026-01-01T00:00:00+00:00",
                line_count=10,
                summary="# Project",
            ),
            DocFile(
                path=".claude/rules/api.md",
                modified_at="2026-01-15T00:00:00+00:00",
                line_count=5,
                summary="Use REST",
            ),
        ],
        dependencies=["flask", "pydantic"],
        recent_commits=["2026-03-01 feat: add sidecar", "2026-02-20 fix: typo"],
        top_dirs=["src", "tests"],
    )


SAMPLE_LLM_ITEMS = [
    LLMReviewItem(
        category=ReviewCategory.staleness,
        severity=ReviewSeverity.high,
        description="CLAUDE.md not updated since Jan 1",
        affected_files=["CLAUDE.md"],
        suggested_action="Review and update CLAUDE.md",
    ),
    LLMReviewItem(
        category=ReviewCategory.gap,
        severity=ReviewSeverity.medium,
        description="No docs for tests/ directory",
        affected_files=[],
        suggested_action="Add testing conventions rule",
    ),
]

SAMPLE_PARSED = LLMReviewResponse(items=SAMPLE_LLM_ITEMS)


def _mock_llm_response(parsed: LLMReviewResponse = SAMPLE_PARSED, tokens: int = 150) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


# ── generate_review ───────────────────────────────────────────────────


def test_generate_review_basic(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()

    result = service.generate_review(scan_result=sample_scan)

    assert len(result.items) == 2
    assert result.items[0].category == "staleness"
    assert result.items[1].category == "gap"
    assert result.tokens_used == 150
    assert result.model_used == "test/cheap-model"


def test_generate_review_writes_review_md(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()

    service.generate_review(scan_result=sample_scan)

    review_path = Path(service._sidecar_dir) / "review.md"
    assert review_path.exists()
    text = review_path.read_text(encoding="utf-8")
    assert "Staleness" in text
    assert "Missing Documentation" in text
    assert "(id: " in text


def test_generate_review_archives(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()

    service.generate_review(scan_result=sample_scan)

    history_dir = service._sidecar_dir / "history"
    assert history_dir.exists()
    archives = list(history_dir.glob("*.md"))
    assert len(archives) == 1


def test_generate_review_tracks_usage(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response(tokens=200)

    service.generate_review(scan_result=sample_scan)

    usage_data = json.loads(service._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 200
    assert usage_data["calls"] == 1


def test_generate_review_accumulates_usage(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response(tokens=100)

    service.generate_review(scan_result=sample_scan)
    service.generate_review(scan_result=sample_scan)

    usage_data = json.loads(service._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 200
    assert usage_data["calls"] == 2


# ── _build_items ──────────────────────────────────────────────────────


def test_build_items_converts_llm_items(service) -> None:
    items = service._build_items(SAMPLE_LLM_ITEMS, {})

    assert len(items) == 2
    assert items[0].category == "staleness"
    assert items[1].category == "gap"
    assert items[0].item_id  # non-empty hash


def test_build_items_filters_suppressed(service) -> None:
    future = datetime.fromtimestamp(
        time.time() + 86400, tz=timezone.utc
    ).isoformat()

    # Get the item_id that would be generated for the first item
    items_all = service._build_items(SAMPLE_LLM_ITEMS, {})
    first_id = items_all[0].item_id

    items = service._build_items(SAMPLE_LLM_ITEMS, {first_id: future})

    assert len(items) == 1
    assert items[0].category == "gap"


def test_build_items_empty_list(service) -> None:
    items = service._build_items([], {})

    assert items == []


def test_generate_review_handles_none_parsed(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))],
        usage=SimpleNamespace(total_tokens=50),
        model="test/cheap-model",
    )

    result = service.generate_review(scan_result=sample_scan)

    assert result.items == []
    assert result.tokens_used == 50


# ── Lock ──────────────────────────────────────────────────────────────


def test_lock_prevents_concurrent_run(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()

    # Manually create a fresh lock
    service._ensure_dirs()
    lock = service._sidecar_dir / ".lock"
    lock.write_text("99999", encoding="utf-8")

    with pytest.raises(RuntimeError, match="lock held"):
        service.generate_review(scan_result=sample_scan)


def test_stale_lock_is_ignored(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()

    # Create a lock older than 60s
    service._ensure_dirs()
    lock = service._sidecar_dir / ".lock"
    lock.write_text("99999", encoding="utf-8")
    import os
    old_time = time.time() - 120
    os.utime(lock, (old_time, old_time))

    # Should not raise — stale lock is overridden
    result = service.generate_review(scan_result=sample_scan)
    assert len(result.items) == 2


def test_lock_released_after_review(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()

    service.generate_review(scan_result=sample_scan)

    lock = service._sidecar_dir / ".lock"
    assert not lock.exists()


def test_lock_released_on_error(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.side_effect = Exception("API error")

    with pytest.raises(Exception, match="API error"):
        service.generate_review(scan_result=sample_scan)

    lock = service._sidecar_dir / ".lock"
    assert not lock.exists()


# ── acknowledge / suppress ────────────────────────────────────────────


def test_acknowledge_creates_suppression(service) -> None:
    service.acknowledge("abc123", days=7)

    suppressed = json.loads(service._suppress_file.read_text(encoding="utf-8"))
    assert "abc123" in suppressed


def test_acknowledge_multiple_items(service) -> None:
    service.acknowledge("item1", days=30)
    service.acknowledge("item2", days=60)

    suppressed = json.loads(service._suppress_file.read_text(encoding="utf-8"))
    assert "item1" in suppressed
    assert "item2" in suppressed


def test_load_suppressed_prunes_expired(service) -> None:
    service._ensure_dirs()
    expired = datetime.fromtimestamp(
        time.time() - 86400, tz=timezone.utc
    ).isoformat()
    valid = datetime.fromtimestamp(
        time.time() + 86400, tz=timezone.utc
    ).isoformat()
    service._suppress_file.write_text(
        json.dumps({"old": expired, "new": valid}), encoding="utf-8"
    )

    result = service._load_suppressed()

    assert "old" not in result
    assert "new" in result


# ── get_status ────────────────────────────────────────────────────────


def test_get_status_no_review(service) -> None:
    status = service.get_status()

    assert status.enabled is True
    assert status.last_run is None
    assert status.pending_items == 0


def test_get_status_with_review(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()
    service.generate_review(scan_result=sample_scan)

    status = service.get_status()

    assert status.last_run is not None
    assert status.pending_items == 2
    assert status.tokens_today == 150


def test_get_status_with_suppression(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = _mock_llm_response()
    service.generate_review(scan_result=sample_scan)
    service.acknowledge("some_item", days=30)

    status = service.get_status()

    assert status.suppressed_items == 1


# ── _write_review_md rendering ────────────────────────────────────────


def test_review_md_no_items(service) -> None:
    from cmdop_claude.models.sidecar import ReviewResult

    result = ReviewResult(
        generated_at="2026-03-06T00:00:00+00:00",
        items=[],
        tokens_used=50,
        model_used="test/model",
    )
    service._ensure_dirs()
    service._write_review_md(result)

    text = (service._sidecar_dir / "review.md").read_text(encoding="utf-8")
    assert "No issues found" in text


def test_review_md_severity_markers(service) -> None:
    from cmdop_claude.models.sidecar import ReviewResult

    result = ReviewResult(
        generated_at="2026-03-06T00:00:00+00:00",
        items=[
            ReviewItem(
                category="staleness",
                severity="high",
                description="Very stale",
                affected_files=["CLAUDE.md"],
                suggested_action="Update it",
                item_id="aaa",
            ),
            ReviewItem(
                category="gap",
                severity="low",
                description="Minor gap",
                affected_files=[],
                suggested_action="Consider adding",
                item_id="bbb",
            ),
        ],
        tokens_used=100,
        model_used="test/model",
    )
    service._ensure_dirs()
    service._write_review_md(result)

    text = (service._sidecar_dir / "review.md").read_text(encoding="utf-8")
    assert "[!]" in text  # high severity
    assert "[~]" in text  # low severity


# ── get_current_review ───────────────────────────────────────────────


def test_get_current_review_no_file(service) -> None:
    assert service.get_current_review() == ""


def test_get_current_review_with_file(service) -> None:
    service._ensure_dirs()
    review_path = service._sidecar_dir / "review.md"
    review_path.write_text("# Review content", encoding="utf-8")

    assert service.get_current_review() == "# Review content"


# ── MCP registration (via claude CLI) ──────────────────────────────

import cmdop_claude.services.sidecar_service._mcp as _mcp_module


def _make_run_fn(get_rc: int = 1, add_rc: int = 0, remove_rc: int = 0):
    """Return a subprocess.run replacement with configurable return codes."""
    from types import SimpleNamespace

    def run(cmd, **kwargs):
        if "get" in cmd:
            return SimpleNamespace(returncode=get_rc, stdout="", stderr="")
        if "add" in cmd:
            return SimpleNamespace(returncode=add_rc, stdout="", stderr="")
        if "remove" in cmd:
            return SimpleNamespace(returncode=remove_rc, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return run


def test_register_mcp_creates_entry(service, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    base = _make_run_fn(get_rc=1, add_rc=0)

    def tracking(cmd, **kwargs):
        calls.append(cmd)
        return base(cmd, **kwargs)

    monkeypatch.setattr(_mcp_module.subprocess, "run", tracking)
    assert service.register_mcp() is True
    assert any("add" in c for c in calls)


def test_register_mcp_idempotent(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=0))
    assert service.register_mcp() is False


def test_unregister_mcp_removes_entry(service, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    base = _make_run_fn(get_rc=0, remove_rc=0)

    def tracking(cmd, **kwargs):
        calls.append(cmd)
        return base(cmd, **kwargs)

    monkeypatch.setattr(_mcp_module.subprocess, "run", tracking)
    assert service.unregister_mcp() is True
    assert any("remove" in c for c in calls)


def test_unregister_mcp_not_registered(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=1))
    assert service.unregister_mcp() is False


def test_is_mcp_registered_true(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=0))
    assert service.is_mcp_registered() is True


def test_is_mcp_registered_false(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=1))
    assert service.is_mcp_registered() is False


# ── fix_task ────────────────────────────────────────────────────────


@pytest.fixture()
def service_with_task(service, tmp_path: Path):
    """Service with a pending task and a CLAUDE.md file."""
    project_root = tmp_path
    claude_md = project_root / "CLAUDE.md"
    claude_md.write_text("# Old content\nFlask project", encoding="utf-8")

    task = service.create_task(
        title="Fix CLAUDE.md",
        description="CLAUDE.md mentions Flask but project uses FastAPI",
        priority="high",
        context_files=["CLAUDE.md"],
    )
    return service, task


def _mock_fix_response(content: str, tokens: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=LLMFixResponse(content=content)
        ))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


def test_fix_task_not_found(service, mock_sdk) -> None:
    result = service.fix_task("T-999")
    assert result.diff == "Task not found."
    assert result.file_path == ""


def test_fix_task_generates_diff(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = _mock_fix_response("# Updated content\nFastAPI project")

    result = svc.fix_task(task.id)

    assert result.file_path == "CLAUDE.md"
    assert "- Flask" in result.diff or "-Flask" in result.diff or "Old content" in result.diff
    assert "+FastAPI" in result.diff or "+ FastAPI" in result.diff or "Updated content" in result.diff
    assert result.applied is False
    assert result.tokens_used == 100


def test_fix_task_apply_writes_file(service_with_task, mock_sdk, tmp_path: Path) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = _mock_fix_response("# Fixed content\nFastAPI project")

    result = svc.fix_task(task.id, apply=True)

    assert result.applied is True
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.read_text(encoding="utf-8") == "# Fixed content\nFastAPI project"


def test_fix_task_apply_marks_completed(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = _mock_fix_response("# Fixed\nNew content")

    svc.fix_task(task.id, apply=True)

    from cmdop_claude.models.task import TaskStatus
    tasks = svc.list_tasks(status="completed")
    assert any(t.id == task.id for t in tasks)


def test_fix_task_no_changes(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = _mock_fix_response("# Old content\nFlask project")

    result = svc.fix_task(task.id)

    assert result.diff == "(no changes needed)"
    assert result.applied is False


def test_fix_task_none_parsed(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))],
        usage=SimpleNamespace(total_tokens=50),
        model="test/cheap-model",
    )

    result = svc.fix_task(task.id)

    assert result.diff == "LLM returned no content."
    assert result.tokens_used == 50


def test_fix_task_tracks_usage(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = _mock_fix_response("# Fixed", tokens=250)

    svc.fix_task(task.id)

    usage_data = json.loads(svc._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 250


def test_fix_task_missing_file_creates_it(service, mock_sdk, tmp_path: Path) -> None:
    """Fix a task targeting a file that doesn't exist yet."""
    task = service.create_task(
        title="Create rules",
        description="Add testing rules",
        priority="medium",
        context_files=[".claude/rules/testing.md"],
    )
    mock_sdk.parse.return_value = _mock_fix_response("# Testing Rules\n- Use pytest")

    result = service.fix_task(task.id, apply=True)

    assert result.applied is True
    new_file = tmp_path / ".claude" / "rules" / "testing.md"
    assert new_file.exists()
    assert "pytest" in new_file.read_text(encoding="utf-8")


# ── init_project ────────────────────────────────────────────────────


def _mock_file_select_response(files: list[str] | None = None) -> SimpleNamespace:
    """Mock Step 1: file selection response."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=LLMFileSelectResponse(files=files or ["pyproject.toml"])
        ))],
        usage=SimpleNamespace(total_tokens=10),
        model="test/cheap-model",
    )


def _mock_init_response(files: list[LLMInitFile], tokens: int = 300) -> SimpleNamespace:
    """Mock Step 2: generate CLAUDE.md + rules response."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=LLMInitResponse(files=files)
        ))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


def test_init_project_skips_existing(service, tmp_path: Path) -> None:
    """Skip if CLAUDE.md already has content."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Existing project docs with more than enough content here!!", encoding="utf-8")

    result = service.init_project()

    assert result.files_created == []
    assert "skipped" in result.model_used


def test_init_project_generates_files(service, mock_sdk, tmp_path: Path) -> None:
    # Step 1: file selection, Step 2: generate (called up to 3 times on retry)
    mock_sdk.parse.side_effect = [
        _mock_file_select_response(["pyproject.toml"]),
        _mock_init_response([
            LLMInitFile(path="CLAUDE.md", content="# My Project\n\n## Tech Stack\n- Python 3.10+\n- FastAPI\n- PostgreSQL\n\n## Commands\n- make test\n- make run\n\n## Architecture\n- src/ — main source code\n"),
            LLMInitFile(path=".claude/rules/api.md", content="# API Rules\n\n- Use REST conventions\n- Return JSON responses\n- Validate with Pydantic\n- Handle errors with HTTPException\n- Use dependency injection\n"),
        ]),
    ]

    result = service.init_project()

    assert len(result.files_created) == 2
    assert "CLAUDE.md" in result.files_created
    assert ".claude/rules/api.md" in result.files_created
    assert result.tokens_used == 300
    assert result.model_used == "test/cheap-model"

    assert (tmp_path / "CLAUDE.md").exists()
    assert "FastAPI" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert (tmp_path / ".claude" / "rules" / "api.md").exists()


def test_init_project_none_parsed_uses_fallback(service, mock_sdk, tmp_path: Path) -> None:
    """When LLM returns None, fallback generates CLAUDE.md from scan data."""
    _none_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))],
        usage=SimpleNamespace(total_tokens=50),
        model="test/cheap-model",
    )
    # Step 1 (file select) succeeds, Step 2 retries 3× returning None
    mock_sdk.parse.side_effect = [
        _mock_file_select_response(),
        _none_resp, _none_resp, _none_resp,
    ]

    result = service.init_project()

    assert result.files_created == ["CLAUDE.md"]
    assert result.tokens_used == 150  # 3 retries × 50 tokens
    assert "fallback" in result.model_used
    assert (tmp_path / "CLAUDE.md").exists()
    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# Project Documentation" in content


def test_init_project_tracks_usage(service, mock_sdk) -> None:
    mock_sdk.parse.side_effect = [
        _mock_file_select_response(),
        _mock_init_response(
            [LLMInitFile(path="CLAUDE.md", content="# Project\n\n## Tech Stack\n- Python\n- FastAPI\n\n## Commands\n- make test\n- make run\n\n## Architecture\n- src/ — source\n")],
            tokens=400,
        ),
    ]

    service.init_project()

    usage_data = json.loads(service._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 400


def test_init_project_creates_subdirs(service, mock_sdk, tmp_path: Path) -> None:
    """Init should create parent directories for nested rule files."""
    mock_sdk.parse.side_effect = [
        _mock_file_select_response(),
        _mock_init_response([
            LLMInitFile(path="CLAUDE.md", content="# Proj\n\n## Tech Stack\n- Python 3.10+\n- FastAPI\n- PostgreSQL\n\n## Commands\n- make test — run tests\n- make run — start server\n\n## Architecture\n- src/ — main source code directory\n"),
            LLMInitFile(path=".claude/rules/deep/nested.md", content="# Deep rule\n\n- Follow coding conventions strictly\n- Use type hints everywhere\n- Write comprehensive tests\n- Handle errors gracefully\n- Document all public APIs\n"),
        ]),
    ]

    result = service.init_project()

    assert (tmp_path / ".claude" / "rules" / "deep" / "nested.md").exists()
