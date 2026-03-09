"""Tests for JSONStorage."""
from pydantic import BaseModel

from cmdop_claude.infrastructure.storage import JSONStorage


class _Config(BaseModel):
    name: str
    value: int = 0


def test_load_returns_none_when_file_missing(tmp_path):
    s = JSONStorage(tmp_path / "missing.json", _Config)
    assert s.load() is None


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "data.json"
    s = JSONStorage(p, _Config)
    s.save(_Config(name="foo", value=42))
    loaded = s.load()
    assert loaded is not None
    assert loaded.name == "foo"
    assert loaded.value == 42


def test_save_creates_parent_dirs(tmp_path):
    p = tmp_path / "a" / "b" / "c.json"
    s = JSONStorage(p, _Config)
    s.save(_Config(name="x"))
    assert p.exists()


def test_load_returns_none_on_corrupt_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    s = JSONStorage(p, _Config)
    assert s.load() is None


def test_load_dict_returns_empty_when_missing(tmp_path):
    s = JSONStorage(tmp_path / "nope.json")
    assert s.load_dict() == {}


def test_save_dict_and_load_dict(tmp_path):
    p = tmp_path / "raw.json"
    s = JSONStorage(p)
    data = {"key": "val", "num": 1}
    s.save_dict(data)
    assert s.load_dict() == data


def test_save_dict_creates_parent_dirs(tmp_path):
    p = tmp_path / "sub" / "raw.json"
    s = JSONStorage(p)
    s.save_dict({"x": 1})
    assert p.exists()


def test_load_dict_returns_empty_on_corrupt_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{broken", encoding="utf-8")
    s = JSONStorage(p)
    assert s.load_dict() == {}


def test_path_property(tmp_path):
    p = tmp_path / "f.json"
    s = JSONStorage(p)
    assert s.path == p
