"""FixService — generate LLM fix for a pending task."""
from __future__ import annotations

import difflib
import json
from pathlib import Path

from cmdop_claude.models.sidecar.fix import FixResult, LLMFixResponse
from cmdop_claude.sidecar.utils.prompts import FIX_SYSTEM, FIX_USER

from .state import SidecarState


class FixService:
    def __init__(self, state: SidecarState) -> None:
        self._s = state

    def fix_task(self, task_id: str, apply: bool = False) -> FixResult:
        tm = self._s.get_task_manager()
        task = tm.get_task(task_id)
        if task is None:
            return FixResult(file_path="", diff="Task not found.")

        target = task.context_files[0] if task.context_files else "CLAUDE.md"
        project_root = self._s.claude_dir.parent
        target_path = project_root / target

        current_content = ""
        if target_path.exists():
            try:
                current_content = target_path.read_text(encoding="utf-8")
            except Exception:
                pass

        tokens_used = 0

        cached = self._load_fix_cache(task_id)
        if cached and cached[0] == target:
            new_content = cached[1]
        else:
            scan_result = self._s.scan()
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

            result = self._s.llm.call(
                model=self._s.model,
                messages=[
                    {"role": "system", "content": FIX_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=LLMFixResponse,
                temperature=0.2,
            )
            tokens_used = result.tokens
            self._s.ensure_dirs()
            self._s.track_usage(tokens_used)
            if not result.parsed:
                return FixResult(file_path=target, diff="LLM returned no content.", tokens_used=tokens_used)
            new_content = result.parsed.content
            self._save_fix_cache(task_id, target, new_content)

        old_lines = current_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=target, tofile=target))
        if not diff:
            diff = "(no changes needed)"

        fix_result = FixResult(file_path=target, diff=diff, tokens_used=tokens_used)

        if apply and diff != "(no changes needed)":
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(new_content, encoding="utf-8")
            fix_result.applied = True
            self._clear_fix_cache(task_id)
            from cmdop_claude.models.skill.task import TaskStatus
            tm.update_status(task_id, TaskStatus.completed)

        self._s.log_activity(
            "fix", tokens=tokens_used,
            task_id=task_id, file=target, applied=fix_result.applied,
        )
        return fix_result

    def _fix_cache_path(self, task_id: str) -> Path:
        return self._s.sidecar_dir / "fix_cache" / f"{task_id}.json"

    def _save_fix_cache(self, task_id: str, file_path: str, new_content: str) -> None:
        cache = self._fix_cache_path(task_id)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps({"file_path": file_path, "content": new_content}),
            encoding="utf-8",
        )

    def _load_fix_cache(self, task_id: str) -> tuple[str, str] | None:
        cache = self._fix_cache_path(task_id)
        if not cache.exists():
            return None
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            return data["file_path"], data["content"]
        except Exception:
            return None

    def _clear_fix_cache(self, task_id: str) -> None:
        cache = self._fix_cache_path(task_id)
        if cache.exists():
            cache.unlink()
