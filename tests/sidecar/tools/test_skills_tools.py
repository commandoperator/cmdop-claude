"""Tests for skills MCP tools."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.skill import SkillFrontmatter


@pytest.fixture(autouse=True)
def patch_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point get_config at a temp .claude dir."""
    from cmdop_claude._config import Config
    cfg = Config(claude_dir_path=str(tmp_path / ".claude"))
    monkeypatch.setattr("cmdop_claude.sidecar.tools.skills_tools.get_config", lambda: cfg)
    return cfg


def _make_skill(name: str = "my-skill", description: str = "Does stuff", manual: bool = False) -> SkillFrontmatter:
    return SkillFrontmatter.model_validate({
        "name": name,
        "description": description,
        "allowed-tools": ["Read"],
        "disable-model-invocation": manual,
    })


@pytest.fixture()
def mock_svc():
    with patch("cmdop_claude.sidecar.tools.skills_tools.SkillService") as mock_cls:
        svc = MagicMock()
        mock_cls.return_value = svc
        yield svc


# ── skills_list ───────────────────────────────────────────────────────


def test_skills_list_empty(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_list

    mock_svc.list_skills.return_value = {}

    result = skills_list()

    assert "No skills" in result


def test_skills_list_returns_skills(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_list

    mock_svc.list_skills.return_value = {
        "pdf": _make_skill("pdf", "Convert files to PDF"),
        "code-reviewer": _make_skill("code-reviewer", "Deep PR review"),
    }

    result = skills_list()

    assert "2" in result
    assert "pdf" in result
    assert "code-reviewer" in result
    assert "Convert files to PDF" in result


def test_skills_list_manual_mode(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_list

    mock_svc.list_skills.return_value = {
        "manual-skill": _make_skill("manual-skill", "Manual only", manual=True),
    }

    result = skills_list()

    assert "manual" in result


# ── skills_get ────────────────────────────────────────────────────────


def test_skills_get_not_found(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_get

    mock_svc.get_skill.return_value = None

    result = skills_get("nonexistent")

    assert "not found" in result


def test_skills_get_returns_content(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_get

    mock_svc.get_skill.return_value = _make_skill("pdf", "Convert files to PDF")
    mock_svc.get_skill_content.return_value = "# PDF Skill\n\nConvert docs to PDF format."

    result = skills_get("pdf")

    assert "pdf" in result.lower()
    assert "Convert files to PDF" in result
    assert "PDF Skill" in result


def test_skills_get_empty_content(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_get

    mock_svc.get_skill.return_value = _make_skill()
    mock_svc.get_skill_content.return_value = ""

    result = skills_get("my-skill")

    assert "no instructions" in result


# ── skills_search ─────────────────────────────────────────────────────


def test_skills_search_no_results(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_search

    mock_svc.search_skills.return_value = {}

    result = skills_search("nonexistent")

    assert "No skills found" in result
    mock_svc.search_skills.assert_called_once_with("nonexistent")


def test_skills_search_returns_matches(mock_svc) -> None:
    from cmdop_claude.sidecar.tools.skills_tools import skills_search

    mock_svc.search_skills.return_value = {
        "pdf": _make_skill("pdf", "Convert files to PDF"),
    }

    result = skills_search("pdf")

    assert "1" in result
    assert "pdf" in result
    assert "Convert files to PDF" in result
