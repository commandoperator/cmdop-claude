"""Tests for sidecar_activity tool."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.sidecar import ActivityEntry


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
    with patch("cmdop_claude.sidecar.tools.init_tools.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def test_sidecar_activity_empty(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_activity

    mock_svc.get_activity.return_value = []

    result = sidecar_activity()

    assert "No activity recorded yet." in result


def test_sidecar_activity_with_entries(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_activity

    mock_svc.get_activity.return_value = [
        ActivityEntry(
            ts=datetime(2026, 3, 6, 14, 30, tzinfo=timezone.utc),
            action="review",
            tokens=200,
            model="deepseek/deepseek-v3.2",
            details={"items": 3},
        ),
        ActivityEntry(
            ts=datetime(2026, 3, 6, 15, 0, tzinfo=timezone.utc),
            action="fix",
            tokens=150,
            model="deepseek/deepseek-v3.2",
            details={"task_id": "T-001"},
        ),
    ]

    result = sidecar_activity()

    assert "2 entries" in result
    assert "review" in result
    assert "fix" in result
    assert "200 tokens" in result
    assert "150 tokens" in result
    assert "2026-03-06" in result
    assert "items=3" in result
    assert "task_id=T-001" in result


def test_sidecar_activity_limit_param(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_activity

    mock_svc.get_activity.return_value = []

    sidecar_activity(limit=5)

    mock_svc.get_activity.assert_called_once_with(limit=5)


def test_sidecar_activity_default_limit(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_activity

    mock_svc.get_activity.return_value = []

    sidecar_activity()

    mock_svc.get_activity.assert_called_once_with(limit=20)
