"""Tests for SkillService — search_skills and import_from_path."""
from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from cmdop_claude._config import Config
from cmdop_claude.services.skill_service import SkillService


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude" / "skills"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def svc(tmp_path: Path) -> SkillService:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    return SkillService(Config(claude_dir_path=str(claude_dir)))


def _write_skill(skills_dir: Path, name: str, display: str, description: str) -> Path:
    d = skills_dir / name
    d.mkdir()
    post = frontmatter.Post(
        "# Instructions",
        name=display,
        description=description,
        **{"allowed-tools": ["Read"]},
        **{"disable-model-invocation": False},
    )
    (d / "SKILL.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    return d


# ── search_skills ─────────────────────────────────────────────────────


def test_search_skills_by_name(svc: SkillService, skills_dir: Path) -> None:
    _write_skill(skills_dir, "pdf", "PDF Converter", "Convert docs to PDF")
    _write_skill(skills_dir, "docx", "DOCX Editor", "Edit Word documents")

    results = svc.search_skills("pdf")

    assert "pdf" in results
    assert "docx" not in results


def test_search_skills_by_description(svc: SkillService, skills_dir: Path) -> None:
    _write_skill(skills_dir, "pdf", "PDF Converter", "Convert docs to PDF")
    _write_skill(skills_dir, "docx", "DOCX Editor", "Edit Word documents")

    results = svc.search_skills("word")

    assert "docx" in results
    assert "pdf" not in results


def test_search_skills_case_insensitive(svc: SkillService, skills_dir: Path) -> None:
    _write_skill(skills_dir, "pdf", "PDF Converter", "Convert docs to PDF")

    assert "pdf" in svc.search_skills("PDF")
    assert "pdf" in svc.search_skills("pdf")
    assert "pdf" in svc.search_skills("Pdf")


def test_search_skills_no_match(svc: SkillService, skills_dir: Path) -> None:
    _write_skill(skills_dir, "pdf", "PDF Converter", "Convert docs to PDF")

    assert svc.search_skills("nonexistent") == {}


def test_search_skills_empty_dir(svc: SkillService) -> None:
    assert svc.search_skills("anything") == {}


# ── import_from_path ──────────────────────────────────────────────────


def test_import_from_path_success(svc: SkillService, tmp_path: Path) -> None:
    src = tmp_path / "my-skill"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: My Skill\n---\n# Instructions", encoding="utf-8")

    result = svc.import_from_path(str(src))

    assert result == "my-skill"
    assert (svc._skills_dir / "my-skill" / "SKILL.md").exists()


def test_import_from_path_no_skill_md(svc: SkillService, tmp_path: Path) -> None:
    src = tmp_path / "empty-dir"
    src.mkdir()

    with pytest.raises(ValueError, match="No SKILL.md"):
        svc.import_from_path(str(src))


def test_import_from_path_already_installed(svc: SkillService, skills_dir: Path, tmp_path: Path) -> None:
    _write_skill(skills_dir, "pdf", "PDF", "PDF tool")

    src = tmp_path / "pdf"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: PDF\n---\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already installed"):
        svc.import_from_path(str(src))


def test_import_copies_all_files(svc: SkillService, tmp_path: Path) -> None:
    src = tmp_path / "rich-skill"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: Rich\n---\n# Rich Skill", encoding="utf-8")
    scripts = src / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text("# helper", encoding="utf-8")

    svc.import_from_path(str(src))

    assert (svc._skills_dir / "rich-skill" / "scripts" / "helper.py").exists()
