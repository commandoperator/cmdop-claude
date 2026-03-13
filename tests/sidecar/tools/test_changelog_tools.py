"""Tests for changelog_list and changelog_get tools."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.services.changelog.changelog_service import ChangelogEntry


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the shared service singleton between tests."""
    import cmdop_claude.sidecar.tools._service_registry as reg
    reg._service = None
    yield
    reg._service = None


@pytest.fixture()
def mock_changelog_svc():
    """Mock ChangelogService so no real filesystem access happens."""
    with patch("cmdop_claude.sidecar.tools.changelog_tools._get_changelog_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def _make_entry(version: str, title: str, release_date: str | None = None) -> ChangelogEntry:
    return ChangelogEntry(
        version=version,
        title=title,
        release_date=date.fromisoformat(release_date) if release_date else None,
        content=f"**Date:** {release_date}\n\n## Changes\n- Some fix\n",
    )


# ── changelog_list ───────────────────────────────────────────────────


def test_changelog_list_empty(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_list

    mock_changelog_svc.list_entries.return_value = []

    result = changelog_list()

    assert "No changelog entries found." in result


def test_changelog_list_returns_entries(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_list

    mock_changelog_svc.list_entries.return_value = [
        _make_entry("0.1.74", "auto-scan background fix", "2026-03-10"),
        _make_entry("0.1.73", "sidecar_add_rule tool", "2026-03-08"),
    ]

    result = changelog_list()

    assert "v0.1.74" in result
    assert "auto-scan background fix" in result
    assert "v0.1.73" in result
    assert "2026-03-10" in result


def test_changelog_list_respects_limit(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_list

    mock_changelog_svc.list_entries.return_value = []

    changelog_list(limit=5)

    mock_changelog_svc.list_entries.assert_called_once_with(limit=5)


# ── changelog_get ────────────────────────────────────────────────────


def test_changelog_get_latest(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_get

    mock_changelog_svc.get_latest.return_value = _make_entry(
        "0.1.74", "auto-scan background fix", "2026-03-10"
    )

    result = changelog_get("latest")

    mock_changelog_svc.get_latest.assert_called_once()
    mock_changelog_svc.get_entry.assert_not_called()
    assert "v0.1.74" in result
    assert "auto-scan background fix" in result


def test_changelog_get_specific_version(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_get

    mock_changelog_svc.get_entry.return_value = _make_entry(
        "0.1.74", "auto-scan background fix", "2026-03-10"
    )

    result = changelog_get("0.1.74")

    mock_changelog_svc.get_entry.assert_called_once_with("0.1.74")
    mock_changelog_svc.get_latest.assert_not_called()
    assert "v0.1.74" in result


def test_changelog_get_not_found(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_get

    mock_changelog_svc.get_entry.return_value = None

    result = changelog_get("9.9.9")

    assert "No changelog entry found for '9.9.9'" in result


def test_changelog_get_latest_not_found(mock_changelog_svc) -> None:
    from cmdop_claude.sidecar.tools.changelog_tools import changelog_get

    mock_changelog_svc.get_latest.return_value = None

    result = changelog_get("latest")

    assert "No changelog entry found for 'latest'" in result
