"""Tests for sidecar_fix tool."""
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.sidecar import FixResult


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


def test_sidecar_fix_task_not_found(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_fix

    mock_svc.fix_task.return_value = FixResult(
        file_path="",
        diff="Task not found.",
        applied=False,
        tokens_used=0,
    )

    result = sidecar_fix("T-001")

    assert "Task T-001 not found." in result


def test_sidecar_fix_dry_run(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_fix

    mock_svc.fix_task.return_value = FixResult(
        file_path="CLAUDE.md",
        diff="-old line\n+new line",
        applied=False,
        tokens_used=150,
    )

    result = sidecar_fix("T-001", apply=False)

    assert "CLAUDE.md" in result
    assert "```diff" in result
    assert "-old line" in result
    assert "Dry run" in result
    assert "sidecar_fix('T-001', apply=True)" in result
    mock_svc.fix_task.assert_called_once_with("T-001", apply=False)


def test_sidecar_fix_applied(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_fix

    mock_svc.fix_task.return_value = FixResult(
        file_path=".claude/rules/python.md",
        diff="-old\n+new",
        applied=True,
        tokens_used=200,
    )

    result = sidecar_fix("T-002", apply=True)

    assert "Applied." in result
    assert "T-002" in result
    assert "marked completed" in result
    mock_svc.fix_task.assert_called_once_with("T-002", apply=True)


def test_sidecar_fix_no_changes_needed(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.task_tools import sidecar_fix

    mock_svc.fix_task.return_value = FixResult(
        file_path="CLAUDE.md",
        diff="(no changes needed)",
        applied=False,
        tokens_used=80,
    )

    result = sidecar_fix("T-003")

    assert "No changes needed." in result
    # Dry-run prompt should NOT appear when there are no changes
    assert "Dry run" not in result
    assert "Applied" not in result
