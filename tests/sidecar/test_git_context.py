"""Tests for GitContextService."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.git_context import (
    GitContext,
    LLMRepoClassification,
    RepoInfo,
    RepoRole,
)
from cmdop_claude.sidecar.git_context import (
    _BOT_EMAIL_RE,
    _cache_key,
    _find_repos,
    _load_cache,
    _merge,
    _save_cache,
    GitContextService,
)


# ── _find_repos ──────────────────────────────────────────────────────


def test_find_repos_finds_root_git(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    repos = _find_repos(tmp_path)
    assert tmp_path in repos


def test_find_repos_finds_nested_submodule(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    submod = tmp_path / "projects" / "django"
    submod.mkdir(parents=True)
    (submod / ".git").mkdir()
    repos = _find_repos(tmp_path)
    assert tmp_path in repos
    assert submod in repos


def test_find_repos_skips_node_modules(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nm = tmp_path / "node_modules" / "react"
    nm.mkdir(parents=True)
    (nm / ".git").mkdir()  # fake git in node_modules
    repos = _find_repos(tmp_path)
    assert not any("node_modules" in str(r) for r in repos)


def test_find_repos_respects_safety_cap(tmp_path: Path) -> None:
    """Creates 60 fake repos but only 50 should be returned."""
    for i in range(60):
        d = tmp_path / f"repo{i}"
        d.mkdir()
        (d / ".git").mkdir()
    repos = _find_repos(tmp_path)
    assert len(repos) <= 50


# ── _merge ───────────────────────────────────────────────────────────


def test_merge_root_repo_adds_active_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    infos = [
        RepoInfo(path=".", active_top_dirs=["src", "tests"], has_commits=True),
        RepoInfo(path="external/lib", active_top_dirs=[], has_commits=True),
    ]
    classifications = [
        LLMRepoClassification(path=".", role=RepoRole.own, reason="root"),
        LLMRepoClassification(path="external/lib", role=RepoRole.external, reason="external"),
    ]
    own_dirs = _merge(infos, classifications, root=tmp_path)
    assert "src" in own_dirs
    assert "tests" in own_dirs
    assert "external" not in own_dirs


def test_merge_filters_files_from_active_dirs(tmp_path: Path) -> None:
    """active_top_dirs may include files (e.g. .gitmodules) — filter them out."""
    (tmp_path / "src").mkdir()
    (tmp_path / ".gitmodules").write_text("")  # file, not dir
    infos = [
        RepoInfo(path=".", active_top_dirs=["src", ".gitmodules"], has_commits=True),
    ]
    classifications = [
        LLMRepoClassification(path=".", role=RepoRole.own, reason="root"),
    ]
    own_dirs = _merge(infos, classifications, root=tmp_path)
    assert "src" in own_dirs
    assert ".gitmodules" not in own_dirs


def test_merge_submodule_adds_top_dir(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "projects").mkdir()
    infos = [
        RepoInfo(path=".", active_top_dirs=["src"], has_commits=True),
        RepoInfo(path="projects/payments", active_top_dirs=["api"], has_commits=True),
    ]
    classifications = [
        LLMRepoClassification(path=".", role=RepoRole.own, reason="root"),
        LLMRepoClassification(path="projects/payments", role=RepoRole.own_submodule, reason="same org"),
    ]
    own_dirs = _merge(infos, classifications, root=tmp_path)
    assert "src" in own_dirs
    assert "projects" in own_dirs  # top-level dir of the submodule


def test_merge_external_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    infos = [
        RepoInfo(path=".", active_top_dirs=["src"], has_commits=True),
        RepoInfo(path="@archive/old", active_top_dirs=["code"], has_commits=True),
    ]
    classifications = [
        LLMRepoClassification(path=".", role=RepoRole.own, reason="root"),
        LLMRepoClassification(path="@archive/old", role=RepoRole.external, reason="archive"),
    ]
    own_dirs = _merge(infos, classifications, root=tmp_path)
    assert "src" in own_dirs
    assert "@archive" not in own_dirs


# ── Bot email filter ─────────────────────────────────────────────────


def test_bot_email_re_matches_dependabot() -> None:
    assert _BOT_EMAIL_RE.search("dependabot[bot]@users.noreply.github.com")


def test_bot_email_re_matches_renovate() -> None:
    assert _BOT_EMAIL_RE.search("renovate@whitesource.io")


def test_bot_email_re_does_not_match_human() -> None:
    assert not _BOT_EMAIL_RE.search("john.doe@company.com")


# ── Hard-rule classification ─────────────────────────────────────────


def test_classify_sync_root_is_always_own(tmp_path: Path) -> None:
    from cmdop_claude.sidecar.git_context import _classify_sync

    mock_sdk = MagicMock()
    info = RepoInfo(path=".", remote_url="git@github.com:org/repo.git", has_commits=True)
    result = _classify_sync(mock_sdk, info, "git@github.com:org/repo.git")
    assert result.role == RepoRole.own
    mock_sdk.complete.assert_not_called()  # hard rule, no LLM needed


def test_classify_sync_archive_path_is_always_external(tmp_path: Path) -> None:
    from cmdop_claude.sidecar.git_context import _classify_sync

    mock_sdk = MagicMock()
    info = RepoInfo(path="@archive/old-frontend", remote_url="", has_commits=True)
    result = _classify_sync(mock_sdk, info, "")
    assert result.role == RepoRole.external
    mock_sdk.complete.assert_not_called()


def test_classify_sync_vendor_path_is_always_external() -> None:
    from cmdop_claude.sidecar.git_context import _classify_sync

    mock_sdk = MagicMock()
    info = RepoInfo(path="@vendor/some-lib", remote_url="https://github.com/lib/lib.git")
    result = _classify_sync(mock_sdk, info, "")
    assert result.role == RepoRole.external


# ── Caching ──────────────────────────────────────────────────────────


def test_cache_roundtrip(tmp_path: Path) -> None:
    ctx = GitContext(
        repos=[RepoInfo(path=".", has_commits=True)],
        classifications=[LLMRepoClassification(path=".", role=RepoRole.own, reason="root")],
        own_top_dirs={"src", "tests"},
    )
    cache_file = tmp_path / "git_context.json"
    _save_cache(cache_file, "abc123", ctx)

    loaded = _load_cache(cache_file, "abc123")
    assert loaded is not None
    assert "src" in loaded.own_top_dirs
    assert "tests" in loaded.own_top_dirs


def test_cache_miss_on_wrong_key(tmp_path: Path) -> None:
    ctx = GitContext(own_top_dirs={"src"})
    cache_file = tmp_path / "git_context.json"
    _save_cache(cache_file, "abc123", ctx)

    loaded = _load_cache(cache_file, "different_key")
    assert loaded is None


def test_cache_miss_on_missing_file(tmp_path: Path) -> None:
    result = _load_cache(tmp_path / "nonexistent.json", "any_key")
    assert result is None


# ── GitContext.to_prompt_block ────────────────────────────────────────


def test_git_context_to_prompt_block_empty() -> None:
    ctx = GitContext()
    block = ctx.to_prompt_block()
    assert "no git repos" in block


def test_repo_info_author_count_default() -> None:
    info = RepoInfo(path=".")
    assert info.author_count == 0


def test_repo_info_author_count_stored() -> None:
    info = RepoInfo(path=".", author_count=5)
    assert info.author_count == 5


def test_repo_info_cache_roundtrip_preserves_author_count(tmp_path: Path) -> None:
    ctx = GitContext(
        repos=[RepoInfo(path=".", has_commits=True, author_count=3)],
        classifications=[LLMRepoClassification(path=".", role=RepoRole.own, reason="root")],
        own_top_dirs={"src"},
    )
    cache_file = tmp_path / "git_ctx.json"
    _save_cache(cache_file, "key1", ctx)
    loaded = _load_cache(cache_file, "key1")
    assert loaded is not None
    assert loaded.repos[0].author_count == 3


def test_git_context_to_prompt_block_with_repos() -> None:
    ctx = GitContext(
        repos=[
            RepoInfo(path=".", remote_url="git@github.com:org/repo.git", has_commits=True),
            RepoInfo(path="projects/api", remote_url="", has_commits=True),
        ],
        classifications=[
            LLMRepoClassification(path=".", role=RepoRole.own, reason="root"),
            LLMRepoClassification(path="projects/api", role=RepoRole.own_submodule, reason="same org"),
        ],
        own_top_dirs={"src", "projects"},
    )
    block = ctx.to_prompt_block()
    assert "./" in block
    assert "own" in block
    assert "projects/api/" in block
    assert "own-submodule" in block
