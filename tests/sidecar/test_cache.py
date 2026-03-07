"""Tests for annotation cache."""
from pathlib import Path

from cmdop_claude.sidecar.cache import AnnotationCache, dir_content_hash
from cmdop_claude.sidecar.exclusions import DirInfo


# ── dir_content_hash ─────────────────────────────────────────────────


def test_hash_deterministic() -> None:
    d = DirInfo(path="src", file_names=("a.py", "b.py"), file_count=2)
    h1 = dir_content_hash(d)
    h2 = dir_content_hash(d)
    assert h1 == h2


def test_hash_changes_on_file_add() -> None:
    d1 = DirInfo(path="src", file_names=("a.py",), file_count=1)
    d2 = DirInfo(path="src", file_names=("a.py", "b.py"), file_count=2)
    assert dir_content_hash(d1) != dir_content_hash(d2)


def test_hash_changes_on_rename() -> None:
    d1 = DirInfo(path="src", file_names=("old.py",), file_count=1)
    d2 = DirInfo(path="src", file_names=("new.py",), file_count=1)
    assert dir_content_hash(d1) != dir_content_hash(d2)


def test_hash_same_for_different_paths() -> None:
    """Same files in different dirs produce the same hash (path-independent)."""
    d1 = DirInfo(path="src", file_names=("a.py", "b.py"), file_count=2)
    d2 = DirInfo(path="lib", file_names=("a.py", "b.py"), file_count=2)
    assert dir_content_hash(d1) == dir_content_hash(d2)


def test_hash_length() -> None:
    d = DirInfo(path="src", file_names=("x.py",), file_count=1)
    assert len(dir_content_hash(d)) == 16


# ── AnnotationCache ──────────────────────────────────────────────────


def test_cache_get_miss(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    assert cache.get("src", "abc123") is None


def test_cache_set_and_get(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    cache.set("src", "abc123", "Main source code")
    assert cache.get("src", "abc123") == "Main source code"


def test_cache_get_stale_hash(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    cache.set("src", "old_hash", "Old annotation")
    assert cache.get("src", "new_hash") is None


def test_cache_save_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache1 = AnnotationCache(path)
    cache1.set("src", "h1", "Source code")
    cache1.set("tests", "h2", "Test suite")
    cache1.save()

    cache2 = AnnotationCache(path)
    assert cache2.get("src", "h1") == "Source code"
    assert cache2.get("tests", "h2") == "Test suite"


def test_cache_prune(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    cache.set("src", "h1", "Source")
    cache.set("old_dir", "h2", "Deleted dir")
    cache.set("tests", "h3", "Tests")

    removed = cache.prune({"src", "tests"})

    assert removed == 1
    assert cache.get("old_dir", "h2") is None
    assert cache.get("src", "h1") == "Source"


def test_cache_prune_empty(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    cache.set("src", "h1", "Source")

    removed = cache.prune({"src"})
    assert removed == 0


def test_cache_size(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    assert cache.size == 0
    cache.set("a", "h1", "x")
    cache.set("b", "h2", "y")
    assert cache.size == 2


def test_cache_overwrite(tmp_path: Path) -> None:
    cache = AnnotationCache(tmp_path / "cache.json")
    cache.set("src", "h1", "Old annotation")
    cache.set("src", "h2", "New annotation")
    assert cache.get("src", "h1") is None  # old hash no longer matches
    assert cache.get("src", "h2") == "New annotation"


def test_cache_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    path.write_text("not json!", encoding="utf-8")
    cache = AnnotationCache(path)
    assert cache.size == 0  # graceful recovery


def test_cache_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "cache.json"
    cache = AnnotationCache(path)
    cache.set("src", "h1", "x")
    cache.save()
    assert path.exists()
