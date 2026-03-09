"""Tests for CmdopConfig — typed ~/.claude/cmdop.json model."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmdop_claude.models.config.cmdop_config import CmdopConfig, CmdopPaths, LLMRouting


def test_load_returns_defaults_when_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH",
        tmp_path / "cmdop.json",
    )
    cfg = CmdopConfig.load()
    assert cfg.sdkrouter_api_key == ""
    assert cfg.llm_routing.mode == "openrouter"
    assert cfg.llm_routing.api_key == ""
    assert cfg.sidecar_model == "deepseek/deepseek-v3.2"
    assert cfg.debug_mode is False


def test_load_reads_camel_case_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text(json.dumps({
        "sdkrouterApiKey": "sk-test-123",
        "sidecarModel": "openai/gpt-4o",
        "debugMode": True,
    }))
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    assert cfg.sdkrouter_api_key == "sk-test-123"
    assert cfg.sidecar_model == "openai/gpt-4o"
    assert cfg.debug_mode is True


def test_legacy_sdkrouter_key_migrated_to_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text(json.dumps({"sdkrouterApiKey": "sk-old-key"}))
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    assert cfg.llm_routing.mode == "sdkrouter"
    assert cfg.llm_routing.api_key == "sk-old-key"


def test_llm_routing_openrouter_defaults() -> None:
    routing = LLMRouting()
    assert routing.mode == "openrouter"
    assert routing.resolved_base_url == "https://openrouter.ai/api/v1"
    assert routing.resolved_model == "deepseek/deepseek-v3-r1"
    assert routing.env_var == "OPENROUTER_API_KEY"


def test_llm_routing_openai_defaults() -> None:
    routing = LLMRouting.model_validate({"mode": "openai"})
    assert routing.resolved_base_url == "https://api.openai.com/v1"
    assert routing.resolved_model == "gpt-4o-mini"
    assert routing.env_var == "OPENAI_API_KEY"


def test_llm_routing_model_override() -> None:
    routing = LLMRouting.model_validate({"mode": "openai", "model": "gpt-4o"})
    assert routing.resolved_model == "gpt-4o"


def test_llm_routing_loaded_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text(json.dumps({
        "llmRouting": {"mode": "openai", "apiKey": "sk-openai-key", "model": "gpt-4o"}
    }))
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    assert cfg.llm_routing.mode == "openai"
    assert cfg.llm_routing.api_key == "sk-openai-key"
    assert cfg.llm_routing.resolved_model == "gpt-4o"


def test_set_llm_routing_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    cfg.set_llm_routing("openrouter", "sk-or-abc")
    data = json.loads(p.read_text())
    assert data["llmRouting"]["apiKey"] == "sk-or-abc"
    # Reload and verify routing is correct
    cfg2 = CmdopConfig.load()
    assert cfg2.llm_routing.mode == "openrouter"
    assert cfg2.llm_routing.api_key == "sk-or-abc"


def test_set_llm_routing_non_default_mode_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    cfg.set_llm_routing("openai", "sk-oa-abc")
    data = json.loads(p.read_text())
    assert data["llmRouting"]["mode"] == "openai"
    assert data["llmRouting"]["apiKey"] == "sk-oa-abc"


def test_load_tolerates_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text("not json {{{{")
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig.load()
    assert cfg.sdkrouter_api_key == ""
    assert cfg.llm_routing.mode == "openrouter"


def test_save_writes_camel_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig(sdkrouter_api_key="sk-abc")
    cfg.save()
    data = json.loads(p.read_text())
    assert data["sdkrouterApiKey"] == "sk-abc"


def test_save_merges_with_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    p.write_text(json.dumps({"existingKey": "keep-me"}))
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
    cfg = CmdopConfig(sdkrouter_api_key="new-key")
    cfg.save()
    data = json.loads(p.read_text())
    assert data["existingKey"] == "keep-me"
    assert data["sdkrouterApiKey"] == "new-key"


def test_set_api_key_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "cmdop.json"
    monkeypatch.setattr("cmdop_claude.models.config.cmdop_config.CMDOP_JSON_PATH", p)
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
