"""Task queue manager — YAML frontmatter + markdown task files."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import frontmatter

from ..models.sidecar import ReviewItem
from ..models.task import SidecarTask, TaskPriority, TaskSource, TaskStatus


class TaskManager:
    """Manages .claude/.sidecar/tasks/ directory."""

    __slots__ = ("_tasks_dir",)

    def __init__(self, tasks_dir: Path) -> None:
        self._tasks_dir = tasks_dir

    def _ensure_dir(self) -> None:
        self._tasks_dir.mkdir(parents=True, exist_ok=True)

    # ── CRUD ─────────────────────────────────────────────────────────

    def create_task(self, task: SidecarTask) -> Path:
        """Write task as YAML frontmatter + markdown file."""
        self._ensure_dir()

        data = task.model_dump(mode="json")
        meta: dict[str, object] = {
            "id": data["id"],
            "priority": data["priority"],
            "status": data["status"],
            "source": data["source"],
            "created_at": data["created_at"],
        }
        if data.get("context_files"):
            meta["context_files"] = data["context_files"]
        if data.get("source_item_id"):
            meta["source_item_id"] = data["source_item_id"]
        if data.get("expires_at"):
            meta["expires_at"] = data["expires_at"]

        post = frontmatter.Post(task.description, **meta)
        post["title"] = task.title

        file_path = self._tasks_dir / f"{task.id}.md"
        file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return file_path

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[SidecarTask]:
        """Read all task files, optionally filter by status."""
        if not self._tasks_dir.exists():
            return []

        tasks: list[SidecarTask] = []
        for md_file in sorted(self._tasks_dir.glob("*.md")):
            task = self._read_task(md_file)
            if task is None:
                continue
            if status is not None and task.status != status:
                continue
            tasks.append(task)
        return tasks

    def get_task(self, task_id: str) -> Optional[SidecarTask]:
        """Read a single task by ID."""
        file_path = self._tasks_dir / f"{task_id}.md"
        if not file_path.exists():
            return None
        return self._read_task(file_path)

    def update_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status in its file. Returns True if updated."""
        file_path = self._tasks_dir / f"{task_id}.md"
        if not file_path.exists():
            return False

        try:
            post = frontmatter.load(str(file_path))
            post["status"] = status.value if isinstance(status, TaskStatus) else str(status)
            if status in (TaskStatus.completed, TaskStatus.dismissed):
                post["completed_at"] = datetime.now(tz=timezone.utc).isoformat()
            file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
            return True
        except Exception:
            return False

    # ── Conversions ──────────────────────────────────────────────────

    def convert_review_items(self, items: list[ReviewItem]) -> list[SidecarTask]:
        """Convert sidecar review items into tasks. Skip if task already exists."""
        existing_source_ids = {
            t.source_item_id
            for t in self.list_tasks()
            if t.source_item_id
        }

        created: list[SidecarTask] = []
        for item in items:
            if item.item_id in existing_source_ids:
                continue

            severity_to_priority = {
                "high": TaskPriority.high,
                "medium": TaskPriority.medium,
                "low": TaskPriority.low,
            }
            priority = severity_to_priority.get(item.severity, TaskPriority.medium)

            task = SidecarTask(
                id=self._next_id(),
                priority=priority,
                title=f"[{item.category}] {item.description[:80]}",
                description=self._build_task_description(item),
                context_files=item.affected_files,
                source=TaskSource.sidecar_review,
                source_item_id=item.item_id,
                created_at=datetime.now(tz=timezone.utc),
            )
            self.create_task(task)
            created.append(task)

        return created

    # ── Summary ──────────────────────────────────────────────────────

    def get_pending_summary(self, max_items: int = 3) -> str:
        """Return top N pending tasks as formatted text for context injection."""
        pending = self.list_tasks(status=TaskStatus.pending)
        if not pending:
            return ""

        # Sort by priority (critical > high > medium > low)
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        pending.sort(key=lambda t: priority_order.get(t.priority, 99))

        top = pending[:max_items]
        lines = [f"Pending sidecar tasks ({len(pending)} total):"]
        for t in top:
            lines.append(f"- [{t.priority}] {t.title} (id: {t.id})")
            if t.context_files:
                lines.append(f"  Files: {', '.join(t.context_files)}")
        return "\n".join(lines)

    # ── Maintenance ──────────────────────────────────────────────────

    def prune_expired(self) -> int:
        """Remove expired tasks. Return count removed."""
        if not self._tasks_dir.exists():
            return 0

        now = datetime.now(tz=timezone.utc)
        removed = 0
        for task in self.list_tasks():
            if task.expires_at and task.expires_at < now and task.status == "pending":
                file_path = self._tasks_dir / f"{task.id}.md"
                if file_path.exists():
                    file_path.unlink()
                    removed += 1
        return removed

    # ── Private ──────────────────────────────────────────────────────

    def _next_id(self) -> str:
        """Generate next task ID: T-001, T-002, etc."""
        existing = self.list_tasks()
        if not existing:
            return "T-001"

        max_num = 0
        for t in existing:
            if t.id.startswith("T-") and t.id[2:].isdigit():
                max_num = max(max_num, int(t.id[2:]))
        return f"T-{max_num + 1:03d}"

    def _read_task(self, file_path: Path) -> Optional[SidecarTask]:
        """Parse a task file into SidecarTask."""
        try:
            post = frontmatter.load(str(file_path))
            meta = post.metadata

            return SidecarTask(
                id=meta["id"],
                priority=meta["priority"],
                status=meta.get("status", "pending"),
                title=meta.get("title", "Untitled"),
                description=post.content,
                context_files=meta.get("context_files", []),
                source=meta.get("source", "manual"),
                source_item_id=meta.get("source_item_id"),
                created_at=meta["created_at"],
                expires_at=meta.get("expires_at"),
                completed_at=meta.get("completed_at"),
            )
        except Exception:
            return None

    @staticmethod
    def _build_task_description(item: ReviewItem) -> str:
        """Build markdown description from a review item."""
        lines = [item.description, ""]
        if item.affected_files:
            lines.append(f"**Files:** {', '.join(item.affected_files)}")
        lines.append(f"\n**Action:** {item.suggested_action}")
        return "\n".join(lines)
