"""Tests for the sidecar hook CLI commands."""
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.docs.project_map import DirAnnotation, ProjectMap


@pytest.fixture()
def mock_svc():
    """Mock SidecarService for hook tests."""
    with patch("cmdop_claude.sidecar.hook.SidecarService") as cls:
        svc = MagicMock()
        cls.return_value = svc
        yield svc


@pytest.fixture()
def mock_config():
    """Mock get_config."""
    with patch("cmdop_claude.sidecar.hook.get_config") as mock_get:
        cfg = MagicMock()
        cfg.claude_dir_path = "/tmp/test/.claude"
        mock_get.return_value = cfg
        yield cfg


# ── map-update ───────────────────────────────────────────────────────


def test_map_update_generates(mock_svc, mock_config, capsys, tmp_path) -> None:
    """map-update generates map when no existing map."""
    mock_config.claude_dir_path = str(tmp_path / ".claude")

    mock_svc.generate_map.return_value = ProjectMap(
        generated_at=datetime.now(tz=timezone.utc),
        project_type="python",
        root_annotation="CLI tool",
        directories=[
            DirAnnotation(path="src", annotation="Source", file_count=5),
        ],
        entry_points=["src/main.py"],
        tokens_used=200,
        model_used="test/cheap",
    )

    from cmdop_claude.sidecar.hook import _handle_map_update

    _handle_map_update(mock_svc, mock_config)

    mock_svc.generate_map.assert_called_once()
    captured = capsys.readouterr()
    assert "1 dirs" in captured.out
    assert "1 entry points" in captured.out


def test_map_update_debounce(mock_svc, mock_config, capsys, tmp_path) -> None:
    """map-update skips if map was updated recently."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    map_path = claude_dir / "project-map.md"
    map_path.write_text("# Map")
    mock_config.claude_dir_path = str(claude_dir)

    from cmdop_claude.sidecar.hook import _handle_map_update

    _handle_map_update(mock_svc, mock_config)

    mock_svc.generate_map.assert_not_called()
    captured = capsys.readouterr()
    assert "Skipped" in captured.out


def test_map_update_runs_after_debounce(mock_svc, mock_config, capsys, tmp_path) -> None:
    """map-update runs if map is older than debounce interval."""
    import os

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    map_path = claude_dir / "project-map.md"
    map_path.write_text("# Map")
    # Set mtime to 120 seconds ago
    old_time = time.time() - 120
    os.utime(map_path, (old_time, old_time))
    mock_config.claude_dir_path = str(claude_dir)

    mock_svc.generate_map.return_value = ProjectMap(
        generated_at=datetime.now(tz=timezone.utc),
        project_type="python",
        root_annotation="CLI",
        directories=[],
        entry_points=[],
        tokens_used=0,
        model_used="cache",
    )

    from cmdop_claude.sidecar.hook import _handle_map_update

    _handle_map_update(mock_svc, mock_config)

    mock_svc.generate_map.assert_called_once()


def test_map_update_error(mock_svc, mock_config, capsys, tmp_path) -> None:
    """map-update handles errors gracefully."""
    mock_config.claude_dir_path = str(tmp_path / ".claude")
    mock_svc.generate_map.side_effect = RuntimeError("SDK failed")

    from cmdop_claude.sidecar.hook import _handle_map_update

    _handle_map_update(mock_svc, mock_config)

    captured = capsys.readouterr()
    assert "Error" in captured.out


# ── inject-tasks ─────────────────────────────────────────────────────


def test_inject_tasks_prints_summary(mock_svc, capsys) -> None:
    """inject-tasks prints pending tasks to stdout."""
    mock_svc.last_action_age.return_value = 100  # recent scan, skip auto-scan
    mock_svc.get_pending_summary.return_value = (
        "Pending sidecar tasks (2 total):\n"
        "- [high] Fix stale docs (id: T-001)\n"
        "- [medium] Add tests (id: T-002)"
    )

    from cmdop_claude.sidecar.hook import _handle_inject_tasks

    _handle_inject_tasks(mock_svc)

    captured = capsys.readouterr()
    assert "T-001" in captured.out
    assert "T-002" in captured.out
    mock_svc.get_pending_summary.assert_called_once_with(max_items=3)


def test_inject_tasks_empty(mock_svc, capsys) -> None:
    """inject-tasks prints nothing when no pending tasks."""
    mock_svc.last_action_age.return_value = 100  # recent scan, skip auto-scan
    mock_svc.get_pending_summary.return_value = ""

    from cmdop_claude.sidecar.hook import _handle_inject_tasks

    with patch("cmdop_claude.sidecar.hook._print_version_line"):
        _handle_inject_tasks(mock_svc)

    captured = capsys.readouterr()
    assert captured.out == ""


# ── auto-scan ───────────────────────────────────────────────────────


def test_inject_tasks_triggers_auto_scan_when_never_ran(mock_svc, capsys) -> None:
    """Auto-scan triggers when review has never been run."""
    mock_svc.last_action_age.return_value = None
    review_result = MagicMock()
    review_result.items = [MagicMock()]
    mock_svc.generate_review.return_value = review_result
    mock_svc.get_pending_summary.return_value = ""

    from cmdop_claude.sidecar.hook import _handle_inject_tasks

    _handle_inject_tasks(mock_svc)

    mock_svc.generate_review.assert_called_once()
    mock_svc.convert_review_to_tasks.assert_called_once_with(review_result.items)


def test_inject_tasks_triggers_auto_scan_when_stale(mock_svc, capsys) -> None:
    """Auto-scan triggers when last review was >24h ago."""
    mock_svc.last_action_age.return_value = 90000  # >86400
    review_result = MagicMock()
    review_result.items = []
    mock_svc.generate_review.return_value = review_result
    mock_svc.get_pending_summary.return_value = ""

    from cmdop_claude.sidecar.hook import _handle_inject_tasks

    _handle_inject_tasks(mock_svc)

    mock_svc.generate_review.assert_called_once()
    mock_svc.convert_review_to_tasks.assert_not_called()  # no items


def test_inject_tasks_skips_auto_scan_when_recent(mock_svc, capsys) -> None:
    """Auto-scan skips when last review was <24h ago."""
    mock_svc.last_action_age.return_value = 3600  # 1h ago
    mock_svc.get_pending_summary.return_value = ""

    from cmdop_claude.sidecar.hook import _handle_inject_tasks

    _handle_inject_tasks(mock_svc)

    mock_svc.generate_review.assert_not_called()


def test_inject_tasks_auto_scan_handles_lock(mock_svc, capsys) -> None:
    """Auto-scan silently skips when lock is held."""
    mock_svc.last_action_age.return_value = None
    mock_svc.generate_review.side_effect = RuntimeError("lock held")
    mock_svc.get_pending_summary.return_value = ""

    from cmdop_claude.sidecar.hook import _handle_inject_tasks

    with patch("cmdop_claude.sidecar.hook._print_version_line"):
        _handle_inject_tasks(mock_svc)

    # No crash, still prints tasks
    captured = capsys.readouterr()
    assert captured.out == ""
