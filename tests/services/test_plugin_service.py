"""Tests for PluginService — mock HTTP, cache, install/uninstall."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude._config import Config
from cmdop_claude.models.plugin import MCPPluginInfo, MCPToolInfo, PluginCacheStore
from cmdop_claude.services.plugin_service import PluginService, _OFFICIAL_INDEX_KEY


def _make_service(tmp_path: Path, **kwargs):
    """Create a PluginService with background fetch disabled."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    defaults = {"claude_dir_path": str(claude_dir), "smithery_api_key": "test-key"}
    defaults.update(kwargs)
    config = Config(**defaults)
    with patch.object(PluginService, "_maybe_start_index_fetch"):
        svc = PluginService(config)
    return svc


@pytest.fixture()
def service(tmp_path: Path):
    return _make_service(tmp_path)


@pytest.fixture()
def claude_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect ~/.claude.json to tmp_path."""
    cj = tmp_path / ".claude.json"
    monkeypatch.setattr("cmdop_claude.services.plugin_service.Path.home", lambda: tmp_path)
    return cj


# ── Smithery search ─────────────────────────────────────────────────


SMITHERY_RESPONSE = json.dumps({
    "servers": [
        {
            "displayName": "Slack",
            "qualifiedName": "@anthropic/slack",
            "description": "Slack integration",
            "version": "1.0.0",
            "installCommand": "npx",
            "args": ["-y", "@anthropic/slack-mcp"],
            "useCount": 5000,
            "tools": [{"name": "send_message", "description": "Send message"}],
            "homepage": "https://example.com/slack",
        }
    ]
}).encode()


def _mock_urlopen(response_data: bytes):
    """Create a mock context manager for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_smithery(mock_urlopen, service) -> None:
    mock_urlopen.return_value = _mock_urlopen(SMITHERY_RESPONSE)

    results = service.search_smithery("slack")

    assert len(results) == 1
    assert results[0].name == "Slack"
    assert results[0].source == "smithery"
    assert results[0].install_count == 5000
    assert len(results[0].tools) == 1
    assert results[0].tools[0].name == "send_message"


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_smithery_no_key(mock_urlopen, tmp_path: Path) -> None:
    """Without smithery_api_key, return empty list silently."""
    svc = _make_service(tmp_path, smithery_api_key="")

    results = svc.search_smithery("slack")

    assert results == []
    mock_urlopen.assert_not_called()


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_smithery_http_error(mock_urlopen, service) -> None:
    mock_urlopen.side_effect = Exception("Connection refused")

    results = service.search_smithery("slack")

    assert results == []


# ── Official search ──────────────────────────────────────────────────


OFFICIAL_RESPONSE = json.dumps({
    "servers": [
        {
            "server": {
                "name": "filesystem",
                "description": "File system access",
                "version": "0.5.0",
                "websiteUrl": "https://example.com/fs",
                "tools": [
                    {"name": "read_file", "description": "Read a file"},
                    {"name": "write_file", "description": "Write a file"},
                ],
            },
            "_meta": {},
        }
    ],
    "metadata": {},
}).encode()


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_official_with_index(mock_urlopen, service) -> None:
    """When index is cached, search_official filters from it instantly."""
    # Pre-populate the index cache
    plugins = service._normalize_official(json.loads(OFFICIAL_RESPONSE))
    service._set_cached(_OFFICIAL_INDEX_KEY, "", plugins)

    results = service.search_official("filesystem")

    assert len(results) == 1
    assert results[0].name == "filesystem"
    assert results[0].source == "official"
    assert len(results[0].tools) == 2
    mock_urlopen.assert_not_called()


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_official_fallback(mock_urlopen, service) -> None:
    """Without cached index, falls back to fetching 1 page."""
    mock_urlopen.return_value = _mock_urlopen(OFFICIAL_RESPONSE)

    results = service.search_official("filesystem")

    assert len(results) == 1
    assert results[0].name == "filesystem"
    assert mock_urlopen.call_count == 1


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_official_http_error(mock_urlopen, service) -> None:
    mock_urlopen.side_effect = Exception("Timeout")

    results = service.search_official("test")

    assert results == []


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_background_index_fetch(mock_urlopen, tmp_path: Path) -> None:
    """_fetch_official_index populates the index cache."""
    mock_urlopen.return_value = _mock_urlopen(OFFICIAL_RESPONSE)

    svc = _make_service(tmp_path)
    svc._fetch_official_index()

    index = svc._get_cached(_OFFICIAL_INDEX_KEY)
    assert index is not None
    assert len(index) == 1
    assert index[0].name == "filesystem"


# ── Combined search ──────────────────────────────────────────────────


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_all(mock_urlopen, service) -> None:
    # Pre-populate official index so it doesn't need HTTP
    official_plugins = service._normalize_official(json.loads(OFFICIAL_RESPONSE))
    service._set_cached(_OFFICIAL_INDEX_KEY, "", official_plugins)

    mock_urlopen.return_value = _mock_urlopen(SMITHERY_RESPONSE)

    results = service.search("", source="all")

    assert len(results) == 2
    sources = {r.source for r in results}
    assert sources == {"smithery", "official"}


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_smithery_only(mock_urlopen, service) -> None:
    mock_urlopen.return_value = _mock_urlopen(SMITHERY_RESPONSE)

    results = service.search("slack", source="smithery")

    assert all(r.source == "smithery" for r in results)


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_search_official_only(mock_urlopen, service) -> None:
    # Pre-populate index
    plugins = service._normalize_official(json.loads(OFFICIAL_RESPONSE))
    service._set_cached(_OFFICIAL_INDEX_KEY, "", plugins)

    results = service.search("fs", source="official")

    assert all(r.source == "official" for r in results)


# ── Cache ────────────────────────────────────────────────────────────


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_cache_prevents_duplicate_fetch(mock_urlopen, service) -> None:
    mock_urlopen.return_value = _mock_urlopen(SMITHERY_RESPONSE)

    service.search_smithery("slack")
    service.search_smithery("slack")

    assert mock_urlopen.call_count == 1


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_cache_expired_refetches(mock_urlopen, service) -> None:
    mock_urlopen.return_value = _mock_urlopen(SMITHERY_RESPONSE)

    # First fetch
    service.search_smithery("slack")

    # Expire the cache manually
    store = service._load_store()
    cache = store.caches["smithery:slack"]
    old_time = datetime.fromtimestamp(time.time() - 7200, tz=timezone.utc).isoformat()
    cache.fetched_at = old_time
    service._save_store(store)

    # Second fetch — cache expired
    service.search_smithery("slack")

    assert mock_urlopen.call_count == 2


def test_clear_cache(service) -> None:
    from cmdop_claude.models.plugin import PluginCache
    store = PluginCacheStore(caches={"test:q": PluginCache(query="q")})
    service._save_store(store)
    assert service._cache_path.exists()

    with patch.object(PluginService, "_maybe_start_index_fetch"):
        service.clear_cache()

    assert not service._cache_path.exists()


@patch("cmdop_claude.services.plugin_service.urllib.request.urlopen")
def test_index_cache_expires_and_refetches(mock_urlopen, service) -> None:
    """When the official index cache expires, background fetch should re-run."""
    mock_urlopen.return_value = _mock_urlopen(OFFICIAL_RESPONSE)

    # Populate index
    service._fetch_official_index()

    # Expire it
    store = service._load_store()
    cache = store.caches[_OFFICIAL_INDEX_KEY]
    old_time = datetime.fromtimestamp(time.time() - 7200, tz=timezone.utc).isoformat()
    cache.fetched_at = old_time
    service._save_store(store)

    # search_official should fallback since index is expired
    mock_urlopen.return_value = _mock_urlopen(OFFICIAL_RESPONSE)
    results = service.search_official("")
    assert len(results) >= 1


# ── Filter ───────────────────────────────────────────────────────────


def test_filter_plugins_by_query() -> None:
    plugins = [
        MCPPluginInfo(name="slack", description="Slack integration"),
        MCPPluginInfo(name="github", description="GitHub tools"),
        MCPPluginInfo(name="filesystem", description="File system access"),
    ]

    filtered = PluginService._filter_plugins(plugins, "slack")
    assert len(filtered) == 1
    assert filtered[0].name == "slack"


def test_filter_plugins_empty_query() -> None:
    plugins = [
        MCPPluginInfo(name="a", description=""),
        MCPPluginInfo(name="b", description=""),
    ]
    filtered = PluginService._filter_plugins(plugins, "")
    assert len(filtered) == 2


def test_filter_plugins_limit() -> None:
    plugins = [MCPPluginInfo(name=f"p{i}", description="match") for i in range(30)]
    filtered = PluginService._filter_plugins(plugins, "match", limit=5)
    assert len(filtered) == 5


# ── Install / Uninstall ──────────────────────────────────────────────


def test_install_plugin(service, claude_json) -> None:
    plugin = MCPPluginInfo(
        name="slack",
        install_command="npx",
        args=["-y", "@anthropic/slack-mcp"],
        env={"SLACK_TOKEN": "xoxb-123"},
    )

    assert service.install_plugin(plugin) is True
    assert claude_json.exists()

    data = json.loads(claude_json.read_text(encoding="utf-8"))
    assert "slack" in data["mcpServers"]
    assert data["mcpServers"]["slack"]["command"] == "npx"
    assert data["mcpServers"]["slack"]["args"] == ["-y", "@anthropic/slack-mcp"]
    assert data["mcpServers"]["slack"]["env"] == {"SLACK_TOKEN": "xoxb-123"}


def test_install_plugin_idempotent(service, claude_json) -> None:
    plugin = MCPPluginInfo(name="slack", install_command="npx")

    assert service.install_plugin(plugin) is True
    assert service.install_plugin(plugin) is False


def test_install_plugin_preserves_existing(service, claude_json) -> None:
    claude_json.write_text(json.dumps({
        "numStartups": 5,
        "mcpServers": {"existing": {"command": "python"}}
    }), encoding="utf-8")

    plugin = MCPPluginInfo(name="new-server", install_command="npx")
    service.install_plugin(plugin)

    data = json.loads(claude_json.read_text(encoding="utf-8"))
    assert data["numStartups"] == 5
    assert "existing" in data["mcpServers"]
    assert "new-server" in data["mcpServers"]


def test_uninstall_plugin(service, claude_json) -> None:
    plugin = MCPPluginInfo(name="slack", install_command="npx")
    service.install_plugin(plugin)

    assert service.uninstall_plugin("slack") is True

    data = json.loads(claude_json.read_text(encoding="utf-8"))
    assert "slack" not in data["mcpServers"]


def test_uninstall_plugin_not_found(service, claude_json) -> None:
    assert service.uninstall_plugin("nonexistent") is False


def test_uninstall_plugin_no_file(service, claude_json) -> None:
    assert service.uninstall_plugin("anything") is False


# ── get_installed_names ──────────────────────────────────────────────


def test_get_installed_names_empty(service, claude_json) -> None:
    names = service.get_installed_names()
    assert names == set()


def test_get_installed_names(service, claude_json) -> None:
    claude_json.write_text(json.dumps({
        "mcpServers": {"slack": {"command": "npx"}, "filesystem": {"command": "npx"}}
    }), encoding="utf-8")

    names = service.get_installed_names()
    assert names == {"slack", "filesystem"}


# ── Normalization edge cases ─────────────────────────────────────────


def test_normalize_smithery_empty(tmp_path: Path) -> None:
    svc = _make_service(tmp_path)
    result = svc._normalize_smithery({})
    assert result == []


def test_normalize_official_empty(tmp_path: Path) -> None:
    svc = _make_service(tmp_path)
    result = svc._normalize_official({"servers": []})
    assert result == []


def test_normalize_smithery_uses_results_key(tmp_path: Path) -> None:
    svc = _make_service(tmp_path)
    result = svc._normalize_smithery({
        "results": [{"displayName": "Test", "description": "A test server"}]
    })
    assert len(result) == 1
    assert result[0].name == "Test"
