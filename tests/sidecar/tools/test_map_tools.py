"""Tests for sidecar map and map_view tools."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.docs.project_map import DirAnnotation, ProjectMap


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
    with patch("cmdop_claude.sidecar.tools.map_tools.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def test_sidecar_map_success(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.map_tools import sidecar_map

    mock_svc.generate_map.return_value = ProjectMap(
        generated_at=datetime.now(tz=timezone.utc),
        project_type="python",
        root_annotation="CLI tool",
        directories=[
            DirAnnotation(path="src", annotation="Source code", file_count=5),
            DirAnnotation(path="tests", annotation="Tests", file_count=3),
        ],
        entry_points=["src/main.py"],
        tokens_used=300,
        model_used="test/cheap",
    )

    result = sidecar_map()

    assert "2 directories" in result
    assert "1 entry points" in result
    assert "python" in result
    assert "300" in result


def test_sidecar_map_error(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.map_tools import sidecar_map

    mock_svc.generate_map.side_effect = RuntimeError("SDK error")

    result = sidecar_map()

    assert "Error" in result


def test_sidecar_map_view_returns_content(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.map_tools import sidecar_map_view

    mock_svc.get_current_map.return_value = "# Project Map\n> python — CLI tool"

    result = sidecar_map_view()

    assert "Project Map" in result


def test_sidecar_map_view_empty(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.map_tools import sidecar_map_view

    mock_svc.get_current_map.return_value = ""

    result = sidecar_map_view()

    assert "No project map available" in result
