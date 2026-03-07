"""Tests for sidecar.scanner — filesystem scanning without LLM."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cmdop_claude.sidecar.scanner import (
    full_scan,
    scan_dependencies,
    scan_doc_files,
    scan_git_log,
    scan_top_dirs,
)


# ── scan_doc_files ────────────────────────────────────────────────────


def test_scan_doc_files_finds_root_claude_md(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    root_md = tmp_path / "CLAUDE.md"
    root_md.write_text("# Project\nLine 2\nLine 3\n", encoding="utf-8")

    result = scan_doc_files(claude_dir)

    assert len(result) == 1
    assert result[0].path == "CLAUDE.md"
    assert result[0].line_count == 3
    assert "# Project" in (result[0].summary or "")


def test_scan_doc_files_finds_nested_md(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "api.md").write_text("Use REST\n", encoding="utf-8")
    (rules_dir / "naming.md").write_text("Use snake_case\n", encoding="utf-8")

    result = scan_doc_files(claude_dir)

    paths = [f.path for f in result]
    assert any("api.md" in p for p in paths)
    assert any("naming.md" in p for p in paths)


def test_scan_doc_files_skips_sidecar_dir(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    sidecar_dir = claude_dir / ".sidecar"
    sidecar_dir.mkdir(parents=True)
    (sidecar_dir / "review.md").write_text("old review\n", encoding="utf-8")

    result = scan_doc_files(claude_dir)

    paths = [f.path for f in result]
    assert not any("review.md" in p for p in paths)


def test_scan_doc_files_empty_dir(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    result = scan_doc_files(claude_dir)

    assert result == []


def test_scan_doc_files_no_claude_dir(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    # Don't create the dir

    result = scan_doc_files(claude_dir)

    assert result == []


# ── scan_dependencies ─────────────────────────────────────────────────


def test_scan_dependencies_requirements_txt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "requirements.txt").write_text(
        "flask>=2.0\nrequests==2.31.0\n# comment\npydantic[email]>=2.0\n",
        encoding="utf-8",
    )

    result = scan_dependencies()

    assert "flask" in result
    assert "requests" in result
    assert "pydantic" in result
    assert len(result) == 3


def test_scan_dependencies_package_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "package.json").write_text(
        json.dumps({
            "dependencies": {"react": "^19.0.0", "next": "^15.0.0"},
            "devDependencies": {"typescript": "^5.0.0"},
        }),
        encoding="utf-8",
    )

    result = scan_dependencies()

    assert "react" in result
    assert "next" in result
    assert "typescript" in result


def test_scan_dependencies_pyproject_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = [\n    "pydantic>=2.6.0",\n    "fastapi>=0.110.0",\n]\n',
        encoding="utf-8",
    )

    result = scan_dependencies()

    assert "pydantic" in result
    assert "fastapi" in result


def test_scan_dependencies_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = scan_dependencies()

    assert result == []


# ── scan_git_log ──────────────────────────────────────────────────────


def test_scan_git_log_success() -> None:
    mock_result = type("R", (), {
        "returncode": 0,
        "stdout": "2026-03-01 feat: add sidecar\n2026-02-28 fix: typo\n",
    })()

    with patch("cmdop_claude.sidecar.scanner.subprocess.run", return_value=mock_result):
        result = scan_git_log(max_entries=5)

    assert len(result) == 2
    assert "feat: add sidecar" in result[0]


def test_scan_git_log_failure() -> None:
    mock_result = type("R", (), {"returncode": 1, "stdout": ""})()

    with patch("cmdop_claude.sidecar.scanner.subprocess.run", return_value=mock_result):
        result = scan_git_log()

    assert result == []


def test_scan_git_log_exception() -> None:
    with patch("cmdop_claude.sidecar.scanner.subprocess.run", side_effect=OSError("no git")):
        result = scan_git_log()

    assert result == []


# ── scan_top_dirs ─────────────────────────────────────────────────────


def test_scan_top_dirs_with_src(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "models").mkdir()
    (src / "services").mkdir()
    (src / "utils").mkdir()

    result = scan_top_dirs("src")

    assert result == ["models", "services", "utils"]


def test_scan_top_dirs_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "node_modules").mkdir()

    result = scan_top_dirs("nonexistent_src")

    assert "app" in result
    assert "tests" in result
    assert ".git" not in result
    assert "node_modules" not in result


# ── full_scan ─────────────────────────────────────────────────────────


def test_full_scan_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    claude_dir = tmp_path / ".claude"
    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text("# Main\n", encoding="utf-8")
    (rules_dir / "style.md").write_text("Use black\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask>=2.0\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api").mkdir()

    with patch("cmdop_claude.sidecar.scanner.scan_git_log", return_value=["2026-03-01 init"]):
        result = full_scan(claude_dir)

    assert len(result.files) == 2  # CLAUDE.md + style.md
    assert "flask" in result.dependencies
    assert result.recent_commits == ["2026-03-01 init"]
    assert "api" in result.top_dirs
