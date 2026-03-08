"""Unit tests for DocsService (SQLite FTS5 backend)."""
from pathlib import Path

import pytest

from cmdop_claude.services.docs_builder import build_db
from cmdop_claude.services.docs_service import DocsService
from cmdop_claude.models.cmdop_config import DocsSource


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    """Build a small docs.db for testing."""
    docs = tmp_path / "src"
    docs.mkdir()
    (docs / "migration-guide.md").write_text(
        "# Migration Guide\nRun `python manage.py migrate` before deploying."
    )
    (docs / "setup.md").write_text(
        "# Setup\nInstall with pip install django. Configure settings.py."
    )
    (docs / "testing.md").write_text(
        "# Testing\nUse pytest for unit tests. Mock external services."
    )
    db = tmp_path / "docs.db"
    build_db(docs, db, "test")
    return db


@pytest.fixture(autouse=True)
def no_bundled_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable bundled docs.db so tests use only their own fixtures."""
    monkeypatch.setattr(DocsService, "_bundled_db_path", lambda self: None)


@pytest.fixture
def svc(sample_db: Path) -> DocsService:
    return DocsService([DocsSource(path=str(sample_db), description="test")])


# ── Search tests ──────────────────────────────────────────────────────


def test_search_finds_by_content(svc: DocsService) -> None:
    results = svc.search("migration")
    assert len(results) >= 1
    paths = [r["path"] for r in results]
    assert any("migration" in p for p in paths)


def test_search_bm25_ranking(svc: DocsService) -> None:
    """migration-guide.md should rank higher than setup.md for 'django'."""
    results = svc.search("django")
    assert len(results) >= 1
    # setup.md has more django content — should appear
    assert any("setup" in r["path"] for r in results)


def test_search_phrase(svc: DocsService) -> None:
    results = svc.search('"manage.py"')
    assert len(results) >= 1


def test_search_prefix(svc: DocsService) -> None:
    # migrat* should match "migrate", "migration"
    results = svc.search("migrat*")
    assert len(results) >= 1


def test_search_no_match(svc: DocsService) -> None:
    results = svc.search("xyznotfound123")
    assert results == []


def test_search_invalid_syntax_doesnt_crash(svc: DocsService) -> None:
    # FTS5 syntax error should return empty, not raise
    results = svc.search("AND OR")
    assert isinstance(results, list)


def test_search_limit(svc: DocsService) -> None:
    results = svc.search("the", limit=2)
    assert len(results) <= 2


def test_search_returns_excerpt(svc: DocsService) -> None:
    results = svc.search("migration")
    assert results[0]["excerpt"] != ""


def test_search_returns_title(svc: DocsService) -> None:
    results = svc.search("migration")
    assert results[0]["title"] != ""


# ── Get tests ─────────────────────────────────────────────────────────


def test_get_returns_content(svc: DocsService) -> None:
    content = svc.get("migration-guide.md")
    assert "manage.py migrate" in content


def test_get_missing_returns_message(svc: DocsService) -> None:
    result = svc.get("nonexistent.md")
    assert "not found" in result.lower()


# ── List all tests ────────────────────────────────────────────────────


def test_list_all(svc: DocsService) -> None:
    docs = svc.list_all()
    assert len(docs) == 3
    paths = [d["path"] for d in docs]
    assert "migration-guide.md" in paths
    assert "setup.md" in paths
    assert "testing.md" in paths


def test_list_all_has_title(svc: DocsService) -> None:
    docs = svc.list_all()
    by_path = {d["path"]: d for d in docs}
    assert by_path["migration-guide.md"]["title"] == "Migration Guide"


# ── Empty / missing sources ───────────────────────────────────────────


def test_empty_sources() -> None:
    svc = DocsService([])
    assert svc.search("anything") == []
    assert svc.list_all() == []
    assert "not found" in svc.get("x.md").lower()


def test_missing_db_path_ignored() -> None:
    svc = DocsService([DocsSource(path="/does/not/exist/docs.db", description="")])
    assert svc.search("anything") == []


# ── Build DB tests ────────────────────────────────────────────────────


def test_build_db_indexes_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\nContent A.")
    (tmp_path / "b.md").write_text("# B\nContent B.")
    db = tmp_path / "out.db"
    count = build_db(tmp_path, db, "test")
    assert count == 2
    assert db.exists()


def test_build_db_overwrites_existing(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# A\nContent.")
    db = tmp_path / "out.db"
    build_db(tmp_path, db, "test")
    build_db(tmp_path, db, "test")  # should not raise
    svc = DocsService([DocsSource(path=str(db), description="")])
    assert len(svc.list_all()) == 1


def test_build_db_converts_mdx(tmp_path: Path) -> None:
    (tmp_path / "page.mdx").write_text(
        "import X from './x'\n\n# Title\n\n<Alert />\n\nBody text here.\n"
    )
    db = tmp_path / "out.db"
    build_db(tmp_path, db, "test")
    svc = DocsService([DocsSource(path=str(db), description="")])
    content = svc.get("page.mdx")
    assert "import X" not in content
    assert "<Alert" not in content
    assert "Body text" in content


# ── MDX static method (unchanged) ────────────────────────────────────


def test_mdx_to_md_strips_imports() -> None:
    text = "import Button from './Button'\n\n# Hello\n\nWorld.\n"
    result = DocsService.mdx_to_md(text)
    assert "import Button" not in result
    assert "Hello" in result
    assert "World" in result


def test_mdx_to_md_unwraps_block_jsx() -> None:
    text = '# Title\n\n<Alert type="info">\n  Important note.\n</Alert>\n\nEnd.\n'
    result = DocsService.mdx_to_md(text)
    assert "<Alert" not in result
    assert "Important note" in result
    assert "End" in result
