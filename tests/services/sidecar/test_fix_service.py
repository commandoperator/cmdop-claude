"""Tests for FixService."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmdop_claude.models.sidecar import LLMFixResponse

from .conftest import mock_fix_response, none_llm_response


@pytest.fixture()
def service_with_task(service, tmp_path: Path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Old content\nFlask project", encoding="utf-8")

    task = service.create_task(
        title="Fix CLAUDE.md",
        description="CLAUDE.md mentions Flask but project uses FastAPI",
        priority="high",
        context_files=["CLAUDE.md"],
    )
    return service, task


def test_fix_task_not_found(service, mock_sdk) -> None:
    result = service.fix_task("T-999")
    assert result.diff == "Task not found."
    assert result.file_path == ""


def test_fix_task_generates_diff(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = mock_fix_response("# Updated content\nFastAPI project")

    result = svc.fix_task(task.id)

    assert result.file_path == "CLAUDE.md"
    assert "Old content" in result.diff or "- Flask" in result.diff
    assert "Updated content" in result.diff or "+FastAPI" in result.diff
    assert result.applied is False
    assert result.tokens_used == 100


def test_fix_task_apply_writes_file(service_with_task, mock_sdk, tmp_path: Path) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = mock_fix_response("# Fixed content\nFastAPI project")

    result = svc.fix_task(task.id, apply=True)

    assert result.applied is True
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# Fixed content\nFastAPI project"


def test_fix_task_apply_marks_completed(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = mock_fix_response("# Fixed\nNew content")

    svc.fix_task(task.id, apply=True)

    tasks = svc.list_tasks(status="completed")
    assert any(t.id == task.id for t in tasks)


def test_fix_task_no_changes(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = mock_fix_response("# Old content\nFlask project")

    result = svc.fix_task(task.id)

    assert result.diff == "(no changes needed)"
    assert result.applied is False


def test_fix_task_none_parsed(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = none_llm_response(tokens=50)

    result = svc.fix_task(task.id)

    assert result.diff == "LLM returned no content."
    assert result.tokens_used == 50


def test_fix_task_tracks_usage(service_with_task, mock_sdk) -> None:
    svc, task = service_with_task
    mock_sdk.parse.return_value = mock_fix_response("# Fixed", tokens=250)

    svc.fix_task(task.id)

    usage_data = json.loads(svc._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 250


def test_fix_task_missing_file_creates_it(service, mock_sdk, tmp_path: Path) -> None:
    task = service.create_task(
        title="Create rules",
        description="Add testing rules",
        priority="medium",
        context_files=[".claude/rules/testing.md"],
    )
    mock_sdk.parse.return_value = mock_fix_response("# Testing Rules\n- Use pytest")

    result = service.fix_task(task.id, apply=True)

    assert result.applied is True
    new_file = tmp_path / ".claude" / "rules" / "testing.md"
    assert new_file.exists()
    assert "pytest" in new_file.read_text(encoding="utf-8")
