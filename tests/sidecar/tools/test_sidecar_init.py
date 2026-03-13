"""Tests for sidecar_init tool."""
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.sidecar import InitResult


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the shared service singleton between tests."""
    import cmdop_claude.sidecar.tools._service_registry as reg
    reg._service = None
    yield
    reg._service = None


@pytest.fixture()
def mock_svc():
    """Mock SidecarService so no real scanning or LLM calls happen."""
    with patch("cmdop_claude.sidecar.tools.init_tools.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def test_sidecar_init_success(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_init

    mock_svc.init_project.return_value = InitResult(
        files_created=["CLAUDE.md", ".claude/rules/python.md"],
        tokens_used=1200,
        model_used="deepseek/deepseek-v3.2",
    )

    result = sidecar_init()

    assert "Initialized 2 files" in result
    assert "CLAUDE.md" in result
    assert ".claude/rules/python.md" in result


def test_sidecar_init_skipped(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_init

    mock_svc.init_project.return_value = InitResult(
        files_created=[],
        tokens_used=0,
        model_used="skipped — CLAUDE.md already exists",
    )

    result = sidecar_init()

    assert result.startswith("Skipped:")
    assert "CLAUDE.md already exists" in result


def test_sidecar_init_shows_model_and_tokens(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_init

    mock_svc.init_project.return_value = InitResult(
        files_created=["CLAUDE.md"],
        tokens_used=4200,
        model_used="openai/gpt-4o-mini",
    )

    result = sidecar_init()

    assert "openai/gpt-4o-mini" in result
    assert "4200" in result
