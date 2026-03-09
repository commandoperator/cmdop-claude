"""Tests for task queue Pydantic models."""
import pytest
from pydantic import ValidationError

from cmdop_claude.models.skill.task import (
    SidecarTask,
    TaskPriority,
    TaskQueue,
    TaskSource,
    TaskStatus,
)


# ── Enums ────────────────────────────────────────────────────────────


def test_task_priority_values() -> None:
    assert TaskPriority.critical == "critical"
    assert TaskPriority.high == "high"
    assert TaskPriority.medium == "medium"
    assert TaskPriority.low == "low"


def test_task_status_values() -> None:
    assert TaskStatus.pending == "pending"
    assert TaskStatus.in_progress == "in_progress"
    assert TaskStatus.completed == "completed"
    assert TaskStatus.dismissed == "dismissed"


def test_task_source_values() -> None:
    assert TaskSource.sidecar_review == "sidecar_review"
    assert TaskSource.manual == "manual"
    assert TaskSource.map_update == "map_update"


# ── SidecarTask ──────────────────────────────────────────────────────


def test_sidecar_task_minimal() -> None:
    task = SidecarTask(
        id="T-001",
        priority="high",
        title="Fix stale docs",
        description="CLAUDE.md is 50 days old",
        source="sidecar_review",
        created_at="2026-03-06T00:00:00Z",
    )
    assert task.status == "pending"
    assert task.context_files == []
    assert task.source_item_id is None
    assert task.expires_at is None
    assert task.completed_at is None


def test_sidecar_task_full() -> None:
    task = SidecarTask(
        id="T-002",
        priority="critical",
        status="in_progress",
        title="Security contradiction",
        description="CLAUDE.md says JWT but code uses OAuth2",
        context_files=["src/auth.ts", ".claude/rules/security.md"],
        source="sidecar_review",
        source_item_id="abc123",
        created_at="2026-03-06T00:00:00Z",
        expires_at="2026-03-16T00:00:00Z",
    )
    assert task.priority == "critical"
    assert task.status == "in_progress"
    assert len(task.context_files) == 2
    assert task.source_item_id == "abc123"


def test_sidecar_task_manual_source() -> None:
    task = SidecarTask(
        id="T-003",
        priority="medium",
        title="Add testing docs",
        description="Developer requested testing guidelines",
        source="manual",
        created_at="2026-03-06T00:00:00Z",
    )
    assert task.source == "manual"


def test_sidecar_task_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        SidecarTask(
            id="",
            priority="high",
            title="x",
            description="x",
            source="manual",
            created_at="2026-03-06T00:00:00Z",
        )


def test_sidecar_task_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        SidecarTask(
            id="T-001",
            priority="high",
            title="",
            description="x",
            source="manual",
            created_at="2026-03-06T00:00:00Z",
        )


def test_sidecar_task_rejects_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        SidecarTask(
            id="T-001",
            priority="urgent",
            title="x",
            description="x",
            source="manual",
            created_at="2026-03-06T00:00:00Z",
        )


def test_sidecar_task_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        SidecarTask(
            id="T-001",
            priority="high",
            status="blocked",
            title="x",
            description="x",
            source="manual",
            created_at="2026-03-06T00:00:00Z",
        )


def test_sidecar_task_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SidecarTask(
            id="T-001",
            priority="high",
            title="x",
            description="x",
            source="manual",
            created_at="2026-03-06T00:00:00Z",
            unknown_field="bad",
        )


def test_sidecar_task_serialization() -> None:
    task = SidecarTask(
        id="T-001",
        priority="high",
        title="Fix docs",
        description="Stale",
        source="sidecar_review",
        created_at="2026-03-06T00:00:00Z",
    )
    data = task.model_dump()
    assert data["id"] == "T-001"
    assert data["priority"] == "high"
    assert data["status"] == "pending"


# ── TaskQueue ────────────────────────────────────────────────────────


def test_task_queue_defaults() -> None:
    q = TaskQueue()
    assert q.total == 0
    assert q.pending == 0
    assert q.in_progress == 0
    assert q.completed == 0
    assert q.dismissed == 0


def test_task_queue_with_counts() -> None:
    q = TaskQueue(total=10, pending=5, in_progress=2, completed=2, dismissed=1)
    assert q.total == 10
    assert q.pending == 5


def test_task_queue_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        TaskQueue(total=-1)
