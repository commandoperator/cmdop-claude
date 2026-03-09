"""Tests for the task queue manager."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmdop_claude.models.sidecar import ReviewItem
from cmdop_claude.models.skill.task import SidecarTask, TaskPriority, TaskSource, TaskStatus
from cmdop_claude.sidecar.tasks.tasks import TaskManager


@pytest.fixture()
def manager(tmp_path: Path) -> TaskManager:
    return TaskManager(tmp_path / "tasks")


def _make_task(**overrides) -> SidecarTask:
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


# ── create_task + get_task ───────────────────────────────────────────


def test_create_task_writes_file(manager: TaskManager) -> None:
    task = _make_task()
    path = manager.create_task(task)

    assert path.exists()
    assert path.name == "T-001.md"

    content = path.read_text(encoding="utf-8")
    assert "Fix stale docs" in content
    assert "CLAUDE.md is 50 days old" in content


def test_create_task_with_context_files(manager: TaskManager) -> None:
    task = _make_task(context_files=["src/auth.ts", ".claude/rules/security.md"])
    path = manager.create_task(task)

    content = path.read_text(encoding="utf-8")
    assert "src/auth.ts" in content


def test_get_task_returns_task(manager: TaskManager) -> None:
    manager.create_task(_make_task())

    task = manager.get_task("T-001")
    assert task is not None
    assert task.id == "T-001"
    assert task.title == "Fix stale docs"
    assert task.priority == "high"
    assert task.status == "pending"


def test_get_task_missing(manager: TaskManager) -> None:
    assert manager.get_task("T-999") is None


def test_create_task_with_source_item_id(manager: TaskManager) -> None:
    task = _make_task(source_item_id="abc123")
    manager.create_task(task)

    loaded = manager.get_task("T-001")
    assert loaded is not None
    assert loaded.source_item_id == "abc123"


def test_create_task_with_expires(manager: TaskManager) -> None:
    future = datetime.now(tz=timezone.utc) + timedelta(days=10)
    task = _make_task(expires_at=future)
    manager.create_task(task)

    loaded = manager.get_task("T-001")
    assert loaded is not None
    assert loaded.expires_at is not None


# ── list_tasks ───────────────────────────────────────────────────────


def test_list_tasks_empty(manager: TaskManager) -> None:
    assert manager.list_tasks() == []


def test_list_tasks_all(manager: TaskManager) -> None:
    manager.create_task(_make_task(id="T-001"))
    manager.create_task(_make_task(id="T-002", title="Second task"))

    tasks = manager.list_tasks()
    assert len(tasks) == 2


def test_list_tasks_filter_by_status(manager: TaskManager) -> None:
    manager.create_task(_make_task(id="T-001"))
    manager.create_task(_make_task(id="T-002", status="completed", title="Done task"))

    pending = manager.list_tasks(status=TaskStatus.pending)
    assert len(pending) == 1
    assert pending[0].id == "T-001"

    completed = manager.list_tasks(status=TaskStatus.completed)
    assert len(completed) == 1
    assert completed[0].id == "T-002"


# ── update_status ────────────────────────────────────────────────────


def test_update_status_completed(manager: TaskManager) -> None:
    manager.create_task(_make_task())

    assert manager.update_status("T-001", TaskStatus.completed) is True

    task = manager.get_task("T-001")
    assert task is not None
    assert task.status == "completed"
    assert task.completed_at is not None


def test_update_status_dismissed(manager: TaskManager) -> None:
    manager.create_task(_make_task())

    assert manager.update_status("T-001", TaskStatus.dismissed) is True

    task = manager.get_task("T-001")
    assert task is not None
    assert task.status == "dismissed"


def test_update_status_missing(manager: TaskManager) -> None:
    assert manager.update_status("T-999", TaskStatus.completed) is False


def test_update_status_in_progress(manager: TaskManager) -> None:
    manager.create_task(_make_task())

    assert manager.update_status("T-001", TaskStatus.in_progress) is True

    task = manager.get_task("T-001")
    assert task is not None
    assert task.status == "in_progress"


# ── convert_review_items ─────────────────────────────────────────────


def test_convert_review_items(manager: TaskManager) -> None:
    items = [
        ReviewItem(
            category="staleness",
            severity="high",
            description="CLAUDE.md is stale",
            affected_files=["CLAUDE.md"],
            suggested_action="Update it",
            item_id="aaa111",
        ),
        ReviewItem(
            category="gap",
            severity="low",
            description="No docs for src/workers/",
            affected_files=[],
            suggested_action="Add docs",
            item_id="bbb222",
        ),
    ]

    created = manager.convert_review_items(items)

    assert len(created) == 2
    assert created[0].priority == "high"
    assert created[0].source_item_id == "aaa111"
    assert created[1].priority == "low"

    # Verify files exist
    tasks = manager.list_tasks()
    assert len(tasks) == 2


def test_convert_review_items_skips_existing(manager: TaskManager) -> None:
    item = ReviewItem(
        category="staleness",
        severity="high",
        description="Stale doc",
        affected_files=["x.md"],
        suggested_action="Fix it",
        item_id="existing123",
    )

    # First conversion
    created1 = manager.convert_review_items([item])
    assert len(created1) == 1

    # Second conversion — should skip
    created2 = manager.convert_review_items([item])
    assert len(created2) == 0

    # Still only 1 task total
    assert len(manager.list_tasks()) == 1


def test_convert_review_items_empty(manager: TaskManager) -> None:
    created = manager.convert_review_items([])
    assert created == []


# ── get_pending_summary ──────────────────────────────────────────────


def test_pending_summary_empty(manager: TaskManager) -> None:
    assert manager.get_pending_summary() == ""


def test_pending_summary_with_tasks(manager: TaskManager) -> None:
    manager.create_task(_make_task(id="T-001", priority="low", title="Low task"))
    manager.create_task(_make_task(id="T-002", priority="high", title="High task"))
    manager.create_task(_make_task(id="T-003", priority="critical", title="Critical task"))

    summary = manager.get_pending_summary(max_items=2)

    assert "3 total" in summary
    # Critical should come first
    lines = summary.splitlines()
    assert "[critical]" in lines[1]
    assert "[high]" in lines[2]


def test_pending_summary_respects_max(manager: TaskManager) -> None:
    for i in range(5):
        manager.create_task(_make_task(id=f"T-{i+1:03d}", title=f"Task {i+1}"))

    summary = manager.get_pending_summary(max_items=2)
    # Should only list 2 tasks but show total 5
    assert "5 total" in summary
    task_lines = [l for l in summary.splitlines() if l.startswith("- ")]
    assert len(task_lines) == 2


# ── prune_expired ────────────────────────────────────────────────────


def test_prune_expired_removes_old(manager: TaskManager) -> None:
    past = datetime.now(tz=timezone.utc) - timedelta(days=1)
    manager.create_task(_make_task(id="T-001", expires_at=past))
    manager.create_task(_make_task(id="T-002"))  # no expiry

    removed = manager.prune_expired()

    assert removed == 1
    assert manager.get_task("T-001") is None
    assert manager.get_task("T-002") is not None


def test_prune_expired_keeps_completed(manager: TaskManager) -> None:
    past = datetime.now(tz=timezone.utc) - timedelta(days=1)
    manager.create_task(_make_task(id="T-001", expires_at=past, status="completed"))

    removed = manager.prune_expired()
    assert removed == 0  # completed tasks not pruned even if expired


def test_prune_expired_empty(manager: TaskManager) -> None:
    assert manager.prune_expired() == 0


# ── _next_id ─────────────────────────────────────────────────────────


def test_next_id_starts_at_001(manager: TaskManager) -> None:
    assert manager._next_id() == "T-001"


def test_next_id_increments(manager: TaskManager) -> None:
    manager.create_task(_make_task(id="T-001"))
    manager.create_task(_make_task(id="T-002", title="Second"))

    assert manager._next_id() == "T-003"
