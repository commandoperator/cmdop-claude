"""Sidecar fix — generate LLM fix for a pending task."""
import difflib

from ...models.sidecar import FixResult, LLMFixResponse
from ...sidecar.prompts import FIX_SYSTEM, FIX_USER
from ._base import SidecarBase


class FixMixin(SidecarBase):
    """Generate and apply documentation fixes."""

    def fix_task(self, task_id: str, apply: bool = False) -> FixResult:
        """Generate a fix for a pending task. Returns diff. Apply if requested."""
        tm = self._get_task_manager()
        task = tm.get_task(task_id)
        if task is None:
            return FixResult(file_path="", diff="Task not found.")

        target = task.context_files[0] if task.context_files else "CLAUDE.md"
        project_root = self._claude_dir.parent
        target_path = project_root / target

        current_content = ""
        if target_path.exists():
            try:
                current_content = target_path.read_text(encoding="utf-8")
            except Exception:
                pass

        scan_result = self.scan()
        deps_block = ", ".join(scan_result.dependencies) or "(none)"
        dirs_block = ", ".join(scan_result.top_dirs) or "(none)"
        commits_block = "\n".join(scan_result.recent_commits[:5]) or "(none)"

        user_msg = FIX_USER.format(
            issue_description=task.description,
            file_path=target,
            current_content=current_content,
            deps_block=deps_block,
            dirs_block=dirs_block,
            commits_block=commits_block,
        )

        response = self._sdk.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": FIX_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format=LLMFixResponse,
            temperature=0.2,
        )

        tokens_used = response.usage.total_tokens if response.usage else 0
        self._ensure_dirs()
        self._track_usage(tokens_used)

        parsed = response.choices[0].message.parsed
        if not parsed:
            return FixResult(file_path=target, diff="LLM returned no content.", tokens_used=tokens_used)

        new_content = parsed.content

        old_lines = current_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=target, tofile=target))

        if not diff:
            diff = "(no changes needed)"

        result = FixResult(file_path=target, diff=diff, tokens_used=tokens_used)

        if apply and diff != "(no changes needed)":
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(new_content, encoding="utf-8")
            result.applied = True
            from ...models.task import TaskStatus
            tm.update_status(task_id, TaskStatus.completed)

        self._log_activity(
            "fix", tokens=tokens_used,
            task_id=task_id, file=target, applied=result.applied,
        )

        return result
