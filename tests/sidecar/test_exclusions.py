"""Tests for sidecar exclusion engine."""
from pathlib import Path

import pytest

from cmdop_claude.sidecar.utils.exclusions import (
    GLOBAL_EXCLUDE_DIRS,
    GLOBAL_EXCLUDE_PATTERNS,
    SENSITIVE_FILES,
    DirInfo,
    is_sensitive_content,
    is_sensitive_file,
    load_gitignore,
    scan_project_dirs,
    should_exclude_dir,
    should_exclude_file,
)


# ── Global sets ──────────────────────────────────────────────────────


def test_global_exclude_dirs_contains_common_junk() -> None:
    for d in ("node_modules", "__pycache__", ".venv", "dist", "build", ".git"):
        assert d in GLOBAL_EXCLUDE_DIRS


def test_global_exclude_patterns_contains_lock_files() -> None:
    assert "*.lock" in GLOBAL_EXCLUDE_PATTERNS
    assert "package-lock.json" in GLOBAL_EXCLUDE_PATTERNS


def test_sensitive_files_contains_env() -> None:
    assert ".env" in SENSITIVE_FILES
    assert ".env.local" in SENSITIVE_FILES
    assert "credentials.json" in SENSITIVE_FILES


# ── should_exclude_dir ───────────────────────────────────────────────


def test_exclude_dir_node_modules() -> None:
    assert should_exclude_dir("node_modules", "node_modules", []) is True


def test_exclude_dir_pycache() -> None:
    assert should_exclude_dir("__pycache__", "src/__pycache__", []) is True


def test_exclude_dir_hidden_dirs() -> None:
    assert should_exclude_dir(".git", ".git", []) is True
    assert should_exclude_dir(".idea", ".idea", []) is True


def test_exclude_dir_hidden_claude() -> None:
    # .claude is a dot-dir, excluded from project scan
    assert should_exclude_dir(".claude", ".claude", []) is True


def test_exclude_dir_normal_dir() -> None:
    assert should_exclude_dir("src", "src", []) is False
    assert should_exclude_dir("tests", "tests", []) is False


def test_exclude_dir_gitignore_pattern() -> None:
    assert should_exclude_dir("generated", "generated", ["generated"]) is True
    assert should_exclude_dir("generated", "generated", []) is False


# ── should_exclude_file ──────────────────────────────────────────────


def test_exclude_file_pyc() -> None:
    assert should_exclude_file("module.pyc", "src/module.pyc", []) is True


def test_exclude_file_lock() -> None:
    assert should_exclude_file("package-lock.json", "package-lock.json", []) is True


def test_exclude_file_sensitive() -> None:
    assert should_exclude_file(".env", ".env", []) is True
    assert should_exclude_file("credentials.json", "credentials.json", []) is True


def test_exclude_file_normal() -> None:
    assert should_exclude_file("main.py", "src/main.py", []) is False
    assert should_exclude_file("index.ts", "src/index.ts", []) is False


def test_exclude_file_gitignore() -> None:
    assert should_exclude_file("output.dat", "data/output.dat", ["*.dat"]) is True


# ── is_sensitive_file ────────────────────────────────────────────────


def test_is_sensitive_env() -> None:
    assert is_sensitive_file(".env") is True
    assert is_sensitive_file(".env.production") is True


def test_is_sensitive_key_files() -> None:
    assert is_sensitive_file("id_rsa") is True
    assert is_sensitive_file("server.pem") is True
    assert is_sensitive_file("cert.key") is True


def test_is_not_sensitive() -> None:
    assert is_sensitive_file("main.py") is False
    assert is_sensitive_file("README.md") is False


# ── is_sensitive_content ─────────────────────────────────────────────


def test_sensitive_content_api_key() -> None:
    assert is_sensitive_content("API_KEY=sk-abc123") is True
    assert is_sensitive_content("api-key: secret123") is True


def test_sensitive_content_private_key() -> None:
    assert is_sensitive_content("-----BEGIN RSA PRIVATE KEY-----") is True


def test_sensitive_content_aws() -> None:
    assert is_sensitive_content("AWS_SECRET_ACCESS_KEY=xxx") is True


def test_sensitive_content_openai_key() -> None:
    assert is_sensitive_content("sk-abcdefghijklmnopqrstuvwx") is True


def test_sensitive_content_github_pat() -> None:
    assert is_sensitive_content("ghp_abcdefghijklmnopqrstuvwxyz1234567890") is True


def test_sensitive_content_database_url() -> None:
    assert is_sensitive_content("DATABASE_URL=postgres://user:pass@host/db") is True


def test_not_sensitive_content() -> None:
    assert is_sensitive_content("def main():") is False
    assert is_sensitive_content("# This is a comment") is False
    assert is_sensitive_content("import os") is False


# ── load_gitignore ───────────────────────────────────────────────────


def test_load_gitignore_basic(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(
        "node_modules\n*.pyc\n# comment\n\n!important.pyc\ndist/\n",
        encoding="utf-8",
    )
    patterns = load_gitignore(tmp_path)
    assert "node_modules" in patterns
    assert "*.pyc" in patterns
    assert "dist" in patterns
    # Comments and negations are skipped
    assert "# comment" not in patterns
    assert "!important.pyc" not in patterns


def test_load_gitignore_missing(tmp_path: Path) -> None:
    assert load_gitignore(tmp_path) == []


# ── DirInfo ──────────────────────────────────────────────────────────


def test_dir_info_depth() -> None:
    assert DirInfo(path=".", file_names=(), file_count=0).depth == 0
    assert DirInfo(path="src", file_names=(), file_count=0).depth == 1
    assert DirInfo(path="src/models", file_names=(), file_count=0).depth == 2
    assert DirInfo(path="src/models/sub", file_names=(), file_count=0).depth == 3


# ── scan_project_dirs ────────────────────────────────────────────────


def test_scan_project_dirs_basic(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("pass", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("pass", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Hello", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path)

    paths = [d.path for d in dirs]
    assert "." in paths  # root
    assert "src" in paths
    assert "tests" in paths


def test_scan_project_dirs_excludes_junk(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("pass", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "react").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "dist").mkdir()

    dirs = scan_project_dirs(tmp_path)

    paths = [d.path for d in dirs]
    assert "node_modules" not in paths
    assert "__pycache__" not in paths
    assert ".git" not in paths
    assert "dist" not in paths
    assert "src" in paths


def test_scan_project_dirs_excludes_sensitive_files(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("pass", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path)

    root_dir = next(d for d in dirs if d.path == ".")
    assert "main.py" in root_dir.file_names
    assert ".env" not in root_dir.file_names
    assert "credentials.json" not in root_dir.file_names


def test_scan_project_dirs_respects_max_depth(tmp_path: Path) -> None:
    # Create deep nesting
    current = tmp_path
    for name in ("a", "b", "c", "d", "e"):
        current = current / name
        current.mkdir()
        (current / "file.txt").write_text("x", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path, max_depth=2)

    paths = [d.path for d in dirs]
    assert "a" in paths
    assert "a/b" in paths
    # depth 3 and beyond should be excluded
    assert "a/b/c" not in paths


def test_scan_project_dirs_respects_max_dirs(tmp_path: Path) -> None:
    for i in range(20):
        d = tmp_path / f"dir_{i:02d}"
        d.mkdir()
        (d / "file.txt").write_text("x", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path, max_dirs=5)

    assert len(dirs) <= 5


def test_scan_project_dirs_respects_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("generated\n*.dat\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("pass", encoding="utf-8")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "output.py").write_text("pass", encoding="utf-8")
    (tmp_path / "data.dat").write_text("x", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path)

    paths = [d.path for d in dirs]
    assert "generated" not in paths
    assert "src" in paths

    # .dat file should be excluded from root file listing
    root = next(d for d in dirs if d.path == ".")
    assert "data.dat" not in root.file_names


def test_scan_project_dirs_skips_empty_subdirs(tmp_path: Path) -> None:
    (tmp_path / "empty_dir").mkdir()
    (tmp_path / "has_files").mkdir()
    (tmp_path / "has_files" / "x.py").write_text("pass", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path)

    paths = [d.path for d in dirs]
    assert "empty_dir" not in paths
    assert "has_files" in paths


def test_scan_project_dirs_file_names_sorted(tmp_path: Path) -> None:
    (tmp_path / "b.py").write_text("pass", encoding="utf-8")
    (tmp_path / "a.py").write_text("pass", encoding="utf-8")
    (tmp_path / "c.py").write_text("pass", encoding="utf-8")

    dirs = scan_project_dirs(tmp_path)

    root = next(d for d in dirs if d.path == ".")
    assert root.file_names == ("a.py", "b.py", "c.py")
