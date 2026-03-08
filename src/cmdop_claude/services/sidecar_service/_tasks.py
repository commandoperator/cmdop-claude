"""Sidecar task management."""
from datetime import datetime, timezone
from typing import Optional

from ...models.sidecar import ReviewItem
from ._base import SidecarBase


class TasksMixin(SidecarBase):
    """Task CRUD operations."""

    def list_tasks(self, status: Optional[str] = None) -> list:
        """List tasks, optionally filtered by status."""
        from ...models.task import TaskStatus

        tm = self._get_task_manager()
        if status is not None:
            return tm.list_tasks(status=TaskStatus(status))
        return tm.list_tasks()

    def create_task(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        context_files: Optional[list[str]] = None,
    ):
        """Create a manual task."""
        from ...models.task import SidecarTask, TaskPriority, TaskSource

        tm = self._get_task_manager()
        task = SidecarTask(
            id=tm._next_id(),
            priority=TaskPriority(priority),
            title=title,
            description=description,
            context_files=context_files or [],
            source=TaskSource.manual,
            created_at=datetime.now(tz=timezone.utc),
        )
        tm.create_task(task)
        return task

    def update_task_status(self, task_id: str, status: str) -> bool:
        """Update a task's status. Returns True if updated."""
        from ...models.task import TaskStatus

        tm = self._get_task_manager()
        return tm.update_status(task_id, TaskStatus(status))

    def get_pending_summary(self, max_items: int = 3) -> str:
        """Get top N pending tasks as formatted text."""
        tm = self._get_task_manager()
        return tm.get_pending_summary(max_items=max_items)

    def convert_review_to_tasks(self, items: list[ReviewItem]) -> list:
        """Convert review items into tasks."""
        tm = self._get_task_manager()
        return tm.convert_review_items(items)
