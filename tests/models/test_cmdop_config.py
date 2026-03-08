"""Tests for CmdopConfig — typed ~/.claude/cmdop.json model."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmdop_claude.models.cmdop_config import CmdopConfig, CmdopPaths


def test_load_returns_defaults_when_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cmdop_claude.models.cmdop_config.CMDOP_JSON_PATH",
        tmp_path / "cmdop.json",
    )
    cfg = CmdopConfig.load()
    assert cfg.sdkrouter_api_key == ""
    assert cfg.sidecar_model == "deepseek/deepseek-v3.2"
    assert cfg.debug_mode is False


def test_load_reads_camel_case_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text(json.dumps({
        "sdkrouterApiKey": "sk-test-123",
        "sidecarModel": "openai/gpt-4o",
        "debugMode": True,
    }))
    monkeypatch.setattr("cmdop_claude.models.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    assert cfg.sdkrouter_api_key == "sk-test-123"
    assert cfg.sidecar_model == "openai/gpt-4o"
    assert cfg.debug_mode is True


def test_load_tolerates_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text("not json {{{{")
    monkeypatch.setattr("cmdop_claude.models.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    assert cfg.sdkrouter_api_key == ""


def test_save_writes_camel_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    monkeypatch.setattr("cmdop_claude.models.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig(sdkrouter_api_key="sk-abc")
    cfg.save()
    data = json.loads(p.read_text())
    assert data["sdkrouterApiKey"] == "sk-abc"


def test_save_merges_with_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text(json.dumps({"existingKey": "keep-me"}))
    monkeypatch.setattr("cmdop_claude.models.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig(sdkrouter_api_key="new-key")
    cfg.save()
    data = json.loads(p.read_text())
    assert data["existingKey"] == "keep-me"
    assert data["sdkrouterApiKey"] == "new-key"


def test_set_api_key_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    monkeypatch.setattr("cmdop_claude.models.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    cfg.set_api_key("sk-persisted")
    data = json.loads(p.read_text())
    assert data["sdkrouterApiKey"] == "sk-persisted"


def test_paths_default_global_dir() -> None:
    paths = CmdopPaths()
    assert paths.global_dir == Path.home() / ".claude" / "cmdop"
    assert paths.plugins_cache == paths.global_dir / "plugins_cache.json"


def test_paths_custom_global_dir(tmp_path: Path) -> None:
    paths = CmdopPaths(global_dir=tmp_path)
    assert paths.plugins_cache == tmp_path / "plugins_cache.json"


def test_config_paths_property_uses_global_dir(tmp_path: Path) -> None:
    cfg = CmdopConfig(global_dir=str(tmp_path))
    assert cfg.paths.global_dir == tmp_path
    assert cfg.paths.plugins_cache == tmp_path / "plugins_cache.json"


def test_config_paths_property_default() -> None:
    cfg = CmdopConfig()
    assert cfg.paths.global_dir == Path.home() / ".claude" / "cmdop"
