"""Tests for sidecar task tools: sidecar_tasks, sidecar_task_update, sidecar_task_create."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.skill.task import SidecarTask


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the shared service singleton between tests."""
    import cmdop_claude.sidecar.tools._service_registry as reg
    reg._service = None
    yield
    reg._service = None


@pytest.fixture()
def mock_svc():
    """Mock SidecarService so no real scanning or LLM calls happen."""
    with patch("cmdop_claude.sidecar.tools.task_tools.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


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


# ── sidecar_tasks ────────────────────────────────────────────────────


def test_sidecar_tasks_list_all(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_tasks

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
    from cmdop_claude.sidecar.tools.task_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = [_make_mock_task()]

    sidecar_tasks(status="pending")

    mock_svc.list_tasks.assert_called_once_with(status="pending")


def test_sidecar_tasks_empty(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = []

    result = sidecar_tasks()

    assert "No tasks found" in result


def test_sidecar_tasks_with_context_files(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_tasks

    mock_svc.list_tasks.return_value = [
        _make_mock_task(context_files=["src/auth.ts", "CLAUDE.md"]),
    ]

    result = sidecar_tasks()

    assert "src/auth.ts" in result


# ── sidecar_task_update ──────────────────────────────────────────────


def test_sidecar_task_update_success(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_task_update

    mock_svc.update_task_status.return_value = True

    result = sidecar_task_update("T-001", "completed")

    assert "updated to completed" in result
    mock_svc.update_task_status.assert_called_once_with("T-001", "completed")


def test_sidecar_task_update_not_found(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_task_update

    mock_svc.update_task_status.return_value = False

    result = sidecar_task_update("T-999", "completed")

    assert "not found" in result


# ── sidecar_task_create ──────────────────────────────────────────────


def test_sidecar_task_create(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_task_create

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
    from cmdop_claude.sidecar.tools.task_tools import sidecar_task_create

    mock_svc.create_task.return_value = _make_mock_task(
        id="T-001", title="Simple task"
    )

    sidecar_task_create(title="Simple task", description="Details")

    mock_svc.create_task.assert_called_once_with(
        title="Simple task",
        description="Details",
        priority="medium",
        context_files=None,
    )
