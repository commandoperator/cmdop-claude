"""Tests for InitService."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cmdop_claude.models.sidecar import LLMInitFile

from .conftest import mock_file_select, mock_init_response, none_llm_response


def test_init_project_skips_existing(service, tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "# Existing project docs with more than enough content here!!", encoding="utf-8"
    )

    result = service.init_project()

    assert result.files_created == []
    assert "skipped" in result.model_used


def test_init_project_generates_files(service, mock_sdk, tmp_path: Path) -> None:
    mock_sdk.parse.side_effect = [
        mock_file_select(["pyproject.toml"]),
        mock_init_response([
            LLMInitFile(path="CLAUDE.md", content="# My Project\n\n## Tech Stack\n- Python 3.10+\n- FastAPI\n- PostgreSQL\n\n## Commands\n- make test\n- make run\n\n## Architecture\n- src/ — main source code\n"),
            LLMInitFile(path=".claude/rules/api.md", content="# API Rules\n\n- Use REST conventions\n- Return JSON responses\n- Validate with Pydantic\n- Handle errors with HTTPException\n- Use dependency injection\n"),
        ]),
    ]

    result = service.init_project()

    assert len(result.files_created) == 2
    assert "CLAUDE.md" in result.files_created
    assert ".claude/rules/api.md" in result.files_created
    assert result.tokens_used == 300
    assert result.model_used

    assert (tmp_path / "CLAUDE.md").exists()
    assert "FastAPI" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert (tmp_path / ".claude" / "rules" / "api.md").exists()


def test_init_project_none_parsed_uses_fallback(service, mock_sdk, tmp_path: Path) -> None:
    mock_sdk.parse.side_effect = [
        mock_file_select(),
        none_llm_response(50), none_llm_response(50), none_llm_response(50),
    ]

    result = service.init_project()

    assert result.files_created == ["CLAUDE.md"]
    assert result.tokens_used == 150
    assert "fallback" in result.model_used
    assert (tmp_path / "CLAUDE.md").exists()
    assert "# Project Documentation" in (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")


def test_init_project_tracks_usage(service, mock_sdk) -> None:
    mock_sdk.parse.side_effect = [
        mock_file_select(),
        mock_init_response(
            [LLMInitFile(path="CLAUDE.md", content="# Project\n\n## Tech Stack\n- Python\n- FastAPI\n\n## Commands\n- make test\n- make run\n\n## Architecture\n- src/ — source\n")],
            tokens=400,
        ),
    ]

    service.init_project()

    usage_data = json.loads(service._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 400


def test_init_project_creates_subdirs(service, mock_sdk, tmp_path: Path) -> None:
    mock_sdk.parse.side_effect = [
        mock_file_select(),
        mock_init_response([
            LLMInitFile(path="CLAUDE.md", content="# Proj\n\n## Tech Stack\n- Python 3.10+\n- FastAPI\n- PostgreSQL\n\n## Commands\n- make test — run tests\n- make run — start server\n\n## Architecture\n- src/ — main source code directory\n"),
            LLMInitFile(path=".claude/rules/deep/nested.md", content="# Deep rule\n\n- Follow coding conventions strictly\n- Use type hints everywhere\n- Write comprehensive tests\n- Handle errors gracefully\n- Document all public APIs\n"),
        ]),
    ]

    result = service.init_project()

    assert (tmp_path / ".claude" / "rules" / "deep" / "nested.md").exists()
