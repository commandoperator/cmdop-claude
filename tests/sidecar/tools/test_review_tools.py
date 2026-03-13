"""Tests for sidecar review/scan/status/acknowledge tools."""
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.sidecar import (
    ReviewItem,
    ReviewResult,
    SidecarStatus,
)


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
    with patch("cmdop_claude.sidecar.tools.review_tools.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def test_sidecar_scan_returns_issues(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_scan

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
    from cmdop_claude.sidecar.tools.review_tools import sidecar_scan

    mock_svc.generate_review.return_value = ReviewResult(
        generated_at="2026-03-06T00:00:00Z",
        items=[],
        tokens_used=100,
        model_used="test/cheap",
    )

    result = sidecar_scan()

    assert "No documentation issues found" in result


def test_sidecar_scan_lock_held(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_scan

    mock_svc.generate_review.side_effect = RuntimeError("lock held")

    result = sidecar_scan()

    assert "Skipped" in result


def test_sidecar_status(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_status

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
    from cmdop_claude.sidecar.tools.review_tools import sidecar_status

    mock_svc.get_status.return_value = SidecarStatus(enabled=True)

    result = sidecar_status()

    assert "Last run: never" in result


def test_sidecar_acknowledge(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_acknowledge

    result = sidecar_acknowledge("abc123", days=7)

    mock_svc.acknowledge.assert_called_once_with("abc123", 7)
    assert "Suppressed abc123 for 7 days" in result


def test_sidecar_acknowledge_default_days(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_acknowledge

    result = sidecar_acknowledge("xyz789")

    mock_svc.acknowledge.assert_called_once_with("xyz789", 30)
    assert "30 days" in result


def test_sidecar_review_returns_content(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_review

    mock_svc.get_current_review.return_value = "# Sidecar Review\n\n## Staleness\n- CLAUDE.md is old"

    result = sidecar_review()

    assert "Sidecar Review" in result
    assert "Staleness" in result


def test_sidecar_review_no_review(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.review_tools import sidecar_review

    mock_svc.get_current_review.return_value = ""

    result = sidecar_review()

    assert "No review available" in result
