"""Tests for PackageIndexer — mocked LLM."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.cmdop_config import PackageSource
from cmdop_claude.models.package_doc import (
    ExportItem,
    PackageLLMExamples,
    PackageLLMOverview,
    UsageExample,
)
from cmdop_claude.services.package_indexer import PackageIndexer, _pkg_index_dir


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_packages_root(tmp_path: Path) -> Path:
    packages = tmp_path / "packages"
    packages.mkdir()

    for pkg_name, pkg_npm in [("ui-core", "@test/ui-core"), ("api", "@test/api")]:
        pkg = packages / pkg_name
        pkg.mkdir()
        (pkg / "package.json").write_text(f'{{"name": "{pkg_npm}", "version": "1.0.0"}}')
        src = pkg / "src"
        src.mkdir()
        (src / "index.ts").write_text(f'export {{ Foo }} from "./foo";\n')
        (pkg / "README.md").write_text(f"# {pkg_npm}\n\nA package.\n")

    # ui-core gets a story
    story = packages / "ui-core" / "src" / "button.story.tsx"
    story.write_text("export const Basic = () => <button>Click</button>;")

    return packages


def _mock_sdk(overview: PackageLLMOverview, examples: PackageLLMExamples | None = None):
    """Build a mock SDKRouter that returns structured output."""
    sdk = MagicMock()

    def _parse(**kwargs):
        response_format = kwargs.get("response_format")
        resp = MagicMock()
        resp.usage.total_tokens = 100
        resp.model = "deepseek/deepseek-v3.2"
        if response_format is PackageLLMOverview:
            resp.choices[0].message.parsed = overview
        elif response_format is PackageLLMExamples:
            resp.choices[0].message.parsed = examples or PackageLLMExamples()
        return resp

    sdk.parse.side_effect = _parse
    return sdk


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_reindex_creates_db(tmp_path: Path) -> None:
    packages = _make_packages_root(tmp_path)
    source = PackageSource(path=str(packages), description="Test packages")

    overview = PackageLLMOverview(
        summary="A test package.",
        install="pnpm add @test/ui-core",
        keywords=["test", "ui"],
        main_exports=[ExportItem(name="Foo", kind="component", description="A foo.", import_path="@test/ui-core")],
    )
    sdk = _mock_sdk(overview)

    indexer = PackageIndexer(sdk=sdk)
    result = indexer.reindex(packages, source)

    assert result.total == 2
    assert len(result.changed) == 2
    assert result.unchanged == []

    db_path = indexer.index_db_path(packages)
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT path, title FROM docs ORDER BY path").fetchall()
    conn.close()

    paths = [r[0] for r in rows]
    assert any("packages/ui-core" in p for p in paths)
    assert any("packages/api" in p for p in paths)


def test_reindex_uses_cache_on_second_run(tmp_path: Path) -> None:
    packages = _make_packages_root(tmp_path)
    source = PackageSource(path=str(packages), description="Test packages")

    overview = PackageLLMOverview(
        summary="A package.", install="pnpm add @test/ui-core", keywords=[], main_exports=[],
    )
    sdk = _mock_sdk(overview)

    indexer = PackageIndexer(sdk=sdk)
    r1 = indexer.reindex(packages, source)
    calls_after_first = sdk.parse.call_count

    r2 = indexer.reindex(packages, source)

    # No new LLM calls on second run (fingerprints unchanged)
    assert sdk.parse.call_count == calls_after_first
    assert len(r2.unchanged) == 2
    assert r2.changed == []


def test_reindex_force_reruns_llm(tmp_path: Path) -> None:
    packages = _make_packages_root(tmp_path)
    source = PackageSource(path=str(packages), description="Test packages")

    overview = PackageLLMOverview(
        summary="A package.", install="pnpm add @test/ui-core", keywords=[], main_exports=[],
    )
    sdk = _mock_sdk(overview)
    indexer = PackageIndexer(sdk=sdk)

    indexer.reindex(packages, source)
    calls_after_first = sdk.parse.call_count

    indexer.reindex(packages, source, force=True)
    assert sdk.parse.call_count > calls_after_first


def test_reindex_with_stories_calls_phase2(tmp_path: Path) -> None:
    packages = _make_packages_root(tmp_path)
    source = PackageSource(path=str(packages), description="Test packages")

    overview = PackageLLMOverview(
        summary="UI package.", install="pnpm add @test/ui-core", keywords=[], main_exports=[],
    )
    examples = PackageLLMExamples(examples=[
        UsageExample(title="Basic", code="<button>Click</button>", component="Button"),
    ])
    sdk = _mock_sdk(overview, examples)
    indexer = PackageIndexer(sdk=sdk)
    indexer.reindex(packages, source)

    db_path = indexer.index_db_path(packages)
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT path FROM docs ORDER BY path").fetchall()
    conn.close()

    paths = [r[0] for r in rows]
    # ui-core has story → should have component-level doc
    assert any("Button" in p for p in paths)


def test_reindex_handles_failed_package(tmp_path: Path) -> None:
    packages = _make_packages_root(tmp_path)
    source = PackageSource(path=str(packages), description="Test packages")

    sdk = MagicMock()
    sdk.parse.side_effect = RuntimeError("LLM unavailable")

    indexer = PackageIndexer(sdk=sdk)
    result = indexer.reindex(packages, source)

    # LLM fails but _llm_overview has a fallback — packages still get indexed
    # with minimal docs (no exception propagated)
    assert result.total == 2
    assert len(result.failed) == 0  # fallback used, not failed
    assert len(result.changed) == 2  # indexed via fallback


def test_index_db_path_is_deterministic(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    packages.mkdir()
    indexer = PackageIndexer(sdk=MagicMock())
    p1 = indexer.index_db_path(packages)
    p2 = indexer.index_db_path(packages)
    assert p1 == p2


def test_fts5_search_works_after_reindex(tmp_path: Path) -> None:
    packages = _make_packages_root(tmp_path)
    source = PackageSource(path=str(packages), description="Test packages")

    overview = PackageLLMOverview(
        summary="Authentication client with JWT and OAuth support.",
        install="pnpm add @test/api",
        keywords=["auth", "jwt", "oauth"],
        main_exports=[
            ExportItem(name="useAuth", kind="hook", description="React hook for auth.", import_path="@test/api"),
        ],
    )
    sdk = _mock_sdk(overview)
    indexer = PackageIndexer(sdk=sdk)
    indexer.reindex(packages, source)

    db_path = indexer.index_db_path(packages)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT path FROM docs WHERE docs MATCH 'auth*' ORDER BY path"
    ).fetchall()
    conn.close()

    assert len(rows) > 0
