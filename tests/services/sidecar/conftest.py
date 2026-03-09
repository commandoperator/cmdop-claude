"""Shared fixtures for sidecar service tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.sidecar import (
    DocFile,
    DocScanResult,
    LLMFileSelectResponse,
    LLMFixResponse,
    LLMInitFile,
    LLMInitResponse,
    LLMReviewItem,
    LLMReviewResponse,
    ReviewCategory,
    ReviewSeverity,
)


@pytest.fixture()
def mock_sdk():
    with patch("cmdop_claude.services.sidecar.state.SDKRouter") as mock_cls:
        sdk_instance = MagicMock()
        mock_cls.return_value = sdk_instance
        yield sdk_instance


@pytest.fixture()
def service(tmp_path: Path, mock_sdk):
    from cmdop_claude._config import Config
    from cmdop_claude.services.sidecar import SidecarService

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    config = Config(claude_dir_path=str(claude_dir))
    return SidecarService(config)


@pytest.fixture()
def sample_scan() -> DocScanResult:
    return DocScanResult(
        files=[
            DocFile(
                path="CLAUDE.md",
                modified_at="2026-01-01T00:00:00+00:00",
                line_count=10,
                summary="# Project",
            ),
            DocFile(
                path=".claude/rules/api.md",
                modified_at="2026-01-15T00:00:00+00:00",
                line_count=5,
                summary="Use REST",
            ),
        ],
        dependencies=["flask", "pydantic"],
        recent_commits=["2026-03-01 feat: add sidecar", "2026-02-20 fix: typo"],
        top_dirs=["src", "tests"],
    )


SAMPLE_LLM_ITEMS = [
    LLMReviewItem(
        category=ReviewCategory.staleness,
        severity=ReviewSeverity.high,
        description="CLAUDE.md not updated since Jan 1",
        affected_files=["CLAUDE.md"],
        suggested_action="Review and update CLAUDE.md",
    ),
    LLMReviewItem(
        category=ReviewCategory.gap,
        severity=ReviewSeverity.medium,
        description="No docs for tests/ directory",
        affected_files=[],
        suggested_action="Add testing conventions rule",
    ),
]

SAMPLE_PARSED = LLMReviewResponse(items=SAMPLE_LLM_ITEMS)


def mock_llm_review(parsed: LLMReviewResponse = SAMPLE_PARSED, tokens: int = 150) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


def mock_fix_response(content: str, tokens: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=LLMFixResponse(content=content)
        ))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


def mock_file_select(files: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=LLMFileSelectResponse(files=files or ["pyproject.toml"])
        ))],
        usage=SimpleNamespace(total_tokens=10),
        model="test/cheap-model",
    )


def mock_init_response(files: list[LLMInitFile], tokens: int = 300) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=LLMInitResponse(files=files)
        ))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


def none_llm_response(tokens: int = 50) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )
