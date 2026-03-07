"""Tests for the project map generator."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.project_map import (
    DirAnnotation,
    LLMDirAnnotation,
    LLMMapResponse,
    MapConfig,
    ProjectMap,
)
from cmdop_claude.sidecar.mapper import ProjectMapper, _ENTRY_NAMES


@pytest.fixture()
def mock_sdk():
    return MagicMock()


@pytest.fixture()
def project(tmp_path: Path):
    """Create a realistic project structure for testing."""
    # .claude dir
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    sidecar_dir = claude_dir / ".sidecar"
    sidecar_dir.mkdir()

    # Source files
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("\"\"\"Main entry.\"\"\"\nprint('hello')\n", encoding="utf-8")
    (src / "utils.py").write_text("\"\"\"Utility functions.\"\"\"\n", encoding="utf-8")

    models = src / "models"
    models.mkdir()
    (models / "user.py").write_text("\"\"\"User model.\"\"\"\n", encoding="utf-8")
    (models / "base.py").write_text("\"\"\"Base model.\"\"\"\n", encoding="utf-8")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test_main(): pass\n", encoding="utf-8")

    # Root files
    (tmp_path / "README.md").write_text("# My Project\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"test\"\n", encoding="utf-8")

    return tmp_path, claude_dir, sidecar_dir


SAMPLE_LLM_RESPONSE = LLMMapResponse(
    project_type="python-package",
    root_summary="A test Python package",
    directories=[
        LLMDirAnnotation(
            path="src",
            annotation="Main source package",
            is_entry_point=True,
            entry_file="main.py",
        ),
        LLMDirAnnotation(
            path="src/models",
            annotation="Pydantic domain models",
            is_entry_point=False,
        ),
        LLMDirAnnotation(
            path="tests",
            annotation="Pytest test suite",
            is_entry_point=False,
        ),
    ],
)


def _mock_llm_response(
    parsed: LLMMapResponse = SAMPLE_LLM_RESPONSE,
    tokens: int = 300,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))],
        usage=SimpleNamespace(total_tokens=tokens),
        model="test/cheap-model",
    )


# ── generate ─────────────────────────────────────────────────────────


def test_generate_creates_map_file(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    result = mapper.generate()

    assert isinstance(result, ProjectMap)
    assert result.project_type == "python-package"
    assert result.root_annotation == "A test Python package"
    assert result.tokens_used == 300
    assert len(result.directories) > 0

    map_path = root / ".claude" / "project-map.md"
    assert map_path.exists()
    text = map_path.read_text(encoding="utf-8")
    assert "# Project Map" in text
    assert "python-package" in text


def test_generate_detects_entry_points(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    result = mapper.generate()

    assert any("main.py" in ep for ep in result.entry_points)


def test_generate_caches_annotations(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    mapper.generate()

    # Cache should exist
    cache_path = sidecar_dir / "map_cache.json"
    assert cache_path.exists()

    # Second call should use cache (no LLM call)
    mock_sdk.parse.reset_mock()
    result2 = mapper.generate()
    mock_sdk.parse.assert_not_called()
    assert result2.tokens_used == 0
    assert result2.model_used == "cache"


def test_generate_calls_llm_for_uncached(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    mapper.generate()

    mock_sdk.parse.assert_called_once()


def test_generate_with_custom_config(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    config = MapConfig(max_depth=1, max_dirs=5)
    result = mapper.generate(config)

    assert isinstance(result, ProjectMap)


def test_generate_handles_none_parsed(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=None))],
        usage=SimpleNamespace(total_tokens=50),
        model="test/cheap-model",
    )

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    result = mapper.generate()

    assert result.project_type == "unknown"
    assert len(result.directories) > 0  # dirs still collected, just default annotations


# ── get_current_map ──────────────────────────────────────────────────


def test_get_current_map_no_file(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)

    assert mapper.get_current_map() == ""


def test_get_current_map_with_file(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    map_path = root / ".claude" / "project-map.md"
    map_path.write_text("# Project Map\ncontent here", encoding="utf-8")

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    assert "Project Map" in mapper.get_current_map()


# ── detect_changes ───────────────────────────────────────────────────


def test_detect_changes_with_git(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)

    mock_result = type("R", (), {
        "returncode": 0,
        "stdout": "src/main.py\nsrc/models/user.py\ntests/test_main.py\n",
    })()

    with patch("cmdop_claude.sidecar.mapper.subprocess.run", return_value=mock_result):
        changed = mapper.detect_changes()

    assert "src" in changed
    assert "src/models" in changed
    assert "tests" in changed


def test_detect_changes_no_git(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)

    with patch("cmdop_claude.sidecar.mapper.subprocess.run", side_effect=OSError("no git")):
        changed = mapper.detect_changes()

    assert changed == []


# ── update_incremental ───────────────────────────────────────────────


def test_update_incremental_uses_cache(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)

    # First call: full generation
    mapper.generate()
    assert mock_sdk.parse.call_count == 1

    # Incremental: should use cache
    mock_sdk.parse.reset_mock()
    result = mapper.update_incremental()
    mock_sdk.parse.assert_not_called()
    assert result.tokens_used == 0


# ── Sensitive content protection ─────────────────────────────────────


def test_snippets_skip_sensitive_files(mock_sdk, tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    sidecar_dir = claude_dir / ".sidecar"
    sidecar_dir.mkdir()

    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, tmp_path, sidecar_dir)
    result = mapper.generate()

    # The LLM call should have been made — check the prompt doesn't contain secrets
    call_args = mock_sdk.parse.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
    user_msg = messages[-1]["content"] if messages else ""
    assert "SECRET=x" not in user_msg


# ── _ENTRY_NAMES ─────────────────────────────────────────────────────


def test_entry_names_contains_common() -> None:
    assert "main.py" in _ENTRY_NAMES
    assert "index.ts" in _ENTRY_NAMES
    assert "main.go" in _ENTRY_NAMES
    assert "Dockerfile" in _ENTRY_NAMES


# ── write_map_md format ──────────────────────────────────────────────


def test_map_md_format(mock_sdk, project) -> None:
    root, claude_dir, sidecar_dir = project
    mock_sdk.parse.return_value = _mock_llm_response()

    mapper = ProjectMapper(mock_sdk, root, sidecar_dir)
    mapper.generate()

    text = (root / ".claude" / "project-map.md").read_text(encoding="utf-8")
    assert "# Project Map" in text
    assert "## Structure" in text
    assert "## Entry Points" in text
    assert "Model: test/cheap-model" in text
    assert "Tokens: 300" in text
