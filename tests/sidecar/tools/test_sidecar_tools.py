"""Tests for the sidecar MCP server tools."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.project_map import DirAnnotation, ProjectMap
from cmdop_claude.models.sidecar import (
    ReviewItem,
    ReviewResult,
    SidecarStatus,
)
from cmdop_claude.models.task import SidecarTask, TaskPriority, TaskSource


@pytest.fixture(autouse=True)
def reset_server_singleton():
    """Reset the module-level _service singleton between tests."""
    import cmdop_claude.sidecar.tools.sidecar_tools as st
    st._service = None
    yield
    st._service = None


@pytest.fixture()
def mock_svc():
    """Mock SidecarService so no real scanning or LLM calls happen."""
    with patch("cmdop_claude.sidecar.tools.sidecar_tools._get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def test_sidecar_scan_returns_issues(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_scan

    mock_svc.generate_review.return_value = ReviewResult(
        generated_at="2026-03-06T00:00:00Z",
        items=[
            ReviewItem(
                category="staleness",
                severity="high",
                description="CLAUDE.md is 50 days old",
                affected_files=["CLAUDE.md"],
                suggested_action="Update it",
                item_id="abc123",
            ),
        ],
        tokens_used=200,
        model_used="test/cheap",
    )

    result = sidecar_scan()

    assert "1 issue(s)" in result
    assert "CLAUDE.md is 50 days old" in result
    assert "test/cheap" in result


def test_sidecar_scan_no_issues(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_scan

    mock_svc.generate_review.return_value = ReviewResult(
        generated_at="2026-03-06T00:00:00Z",
        items=[],
        tokens_used=100,
        model_used="test/cheap",
    )

    result = sidecar_scan()

    assert "No documentation issues found" in result


def test_sidecar_scan_lock_held(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_scan

    mock_svc.generate_review.side_effect = RuntimeError("lock held")

    result = sidecar_scan()

    assert "Skipped" in result


def test_sidecar_status(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_status

    mock_svc.get_status.return_value = SidecarStatus(
        enabled=True,
        last_run="2026-03-06T14:00:00Z",
        pending_items=3,
        suppressed_items=1,
        tokens_today=500,
        cost_today_usd=0.000125,
    )

    result = sidecar_status()

    assert "Pending items: 3" in result
    assert "Suppressed items: 1" in result
    assert "Tokens today: 500" in result


def test_sidecar_status_never_run(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_status

    mock_svc.get_status.return_value = SidecarStatus(enabled=True)

    result = sidecar_status()

    assert "Last run: never" in result


def test_sidecar_acknowledge(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_acknowledge

    result = sidecar_acknowledge("abc123", days=7)

    mock_svc.acknowledge.assert_called_once_with("abc123", 7)
    assert "Suppressed abc123 for 7 days" in result


def test_sidecar_acknowledge_default_days(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_acknowledge

    result = sidecar_acknowledge("xyz789")

    mock_svc.acknowledge.assert_called_once_with("xyz789", 30)
    assert "30 days" in result


def test_sidecar_review_returns_content(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_review

    mock_svc.get_current_review.return_value = "# Sidecar Review\n\n## Staleness\n- CLAUDE.md is old"

    result = sidecar_review()

    assert "Sidecar Review" in result
    assert "Staleness" in result


def test_sidecar_review_no_review(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_review

    mock_svc.get_current_review.return_value = ""

    result = sidecar_review()

    assert "No review available" in result


# ── sidecar_map ──────────────────────────────────────────────────────


def test_sidecar_map_success(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_map

    mock_svc.generate_map.return_value = ProjectMap(
        generated_at=datetime.now(tz=timezone.utc),
        project_type="python",
        root_annotation="CLI tool",
        directories=[
            DirAnnotation(path="src", annotation="Source code", file_count=5),
            DirAnnotation(path="tests", annotation="Tests", file_count=3),
        ],
        entry_points=["src/main.py"],
        tokens_used=300,
        model_used="test/cheap",
    )

    result = sidecar_map()

    assert "2 directories" in result
    assert "1 entry points" in result
    assert "python" in result
    assert "300" in result


def test_sidecar_map_error(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_map

    mock_svc.generate_map.side_effect = RuntimeError("SDK error")

    result = sidecar_map()

    assert "Error" in result


# ── sidecar_map_view ─────────────────────────────────────────────────


def test_sidecar_map_view_returns_content(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_map_view

    mock_svc.get_current_map.return_value = "# Project Map\n> python — CLI tool"

    result = sidecar_map_view()

    assert "Project Map" in result


def test_sidecar_map_view_empty(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_map_view

    mock_svc.get_current_map.return_value = ""

    result = sidecar_map_view()

    assert "No project map available" in result


# ── sidecar_tasks ────────────────────────────────────────────────────


def _make_mock_task(**overrides) -> SidecarTask:
    defaults = dict(
        id="T-001",
        priority="high",
        title="Fix stale docs",
        description="CLAUDE.md is 50 days old",
        source="sidecar_review",
        created_at=datetime.now(tz=timezone.utc),
    )
    defaults.update(overrides)
    return SidecarTask(**defaults)


def test_sidecar_tasks_list_all(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = [
        _make_mock_task(id="T-001"),
        _make_mock_task(id="T-002", title="Add tests"),
    ]

    result = sidecar_tasks()

    assert "2" in result
    assert "T-001" in result
    assert "T-002" in result
    mock_svc.list_tasks.assert_called_once_with(status=None)


def test_sidecar_tasks_filter_by_status(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = [_make_mock_task()]

    result = sidecar_tasks(status="pending")

    mock_svc.list_tasks.assert_called_once_with(status="pending")


def test_sidecar_tasks_empty(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = []

    result = sidecar_tasks()

    assert "No tasks found" in result


def test_sidecar_tasks_with_context_files(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = [
        _make_mock_task(context_files=["src/auth.ts", "CLAUDE.md"]),
    ]

    result = sidecar_tasks()

    assert "src/auth.ts" in result


# ── sidecar_task_update ──────────────────────────────────────────────


def test_sidecar_task_update_success(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_task_update

    mock_svc.update_task_status.return_value = True

    result = sidecar_task_update("T-001", "completed")

    assert "updated to completed" in result
    mock_svc.update_task_status.assert_called_once_with("T-001", "completed")


def test_sidecar_task_update_not_found(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_task_update

    mock_svc.update_task_status.return_value = False

    result = sidecar_task_update("T-999", "completed")

    assert "not found" in result


# ── sidecar_task_create ──────────────────────────────────────────────


def test_sidecar_task_create(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_task_create

    mock_svc.create_task.return_value = _make_mock_task(
        id="T-005", title="New task", priority="high"
    )

    result = sidecar_task_create(
        title="New task",
        description="Do something",
        priority="high",
        context_files=["src/main.py"],
    )

    assert "T-005" in result
    assert "New task" in result
    mock_svc.create_task.assert_called_once_with(
        title="New task",
        description="Do something",
        priority="high",
        context_files=["src/main.py"],
    )


def test_sidecar_task_create_defaults(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.sidecar_tools import sidecar_task_create

    mock_svc.create_task.return_value = _make_mock_task(
        id="T-001", title="Simple task"
    )

    result = sidecar_task_create(title="Simple task", description="Details")

    mock_svc.create_task.assert_called_once_with(
        title="Simple task",
        description="Details",
        priority="medium",
        context_files=None,
    )
