"""Tests for plugin models."""
import time
from datetime import datetime, timezone

from cmdop_claude.models.plugin import (
    MCPPluginInfo,
    MCPToolInfo,
    PluginCache,
    PluginCacheStore,
)


def test_mcp_tool_info_defaults() -> None:
    t = MCPToolInfo(name="read_file")
    assert t.name == "read_file"
    assert t.description == ""


def test_mcp_plugin_info_defaults() -> None:
    p = MCPPluginInfo(name="filesystem")
    assert p.name == "filesystem"
    assert p.source == "official"
    assert p.tools == []
    assert p.install_count == 0
    assert p.args == []
    assert p.env == {}


def test_mcp_plugin_info_smithery() -> None:
    p = MCPPluginInfo(
        name="slack",
        qualified_name="@anthropic/slack",
        description="Slack MCP server",
        source="smithery",
        install_count=5000,
        tools=[MCPToolInfo(name="send_message", description="Send a Slack message")],
    )
    assert p.source == "smithery"
    assert len(p.tools) == 1
    assert p.tools[0].name == "send_message"


def test_plugin_cache_fresh() -> None:
    now = datetime.now(timezone.utc).isoformat()
    cache = PluginCache(
        fetched_at=now,
        ttl_seconds=3600,
        plugins=[MCPPluginInfo(name="test")],
        query="test",
    )
    assert not cache.is_expired()


def test_plugin_cache_expired() -> None:
    old = datetime.fromtimestamp(
        time.time() - 7200, tz=timezone.utc
    ).isoformat()
    cache = PluginCache(
        fetched_at=old,
        ttl_seconds=3600,
        plugins=[],
        query="test",
    )
    assert cache.is_expired()


def test_plugin_cache_empty_fetched_at() -> None:
    cache = PluginCache(query="test")
    assert cache.is_expired()


def test_plugin_cache_store() -> None:
    store = PluginCacheStore()
    assert store.caches == {}

    store.caches["smithery:slack"] = PluginCache(
        fetched_at=datetime.now(timezone.utc).isoformat(),
        plugins=[MCPPluginInfo(name="slack", source="smithery")],
        query="slack",
    )
    assert "smithery:slack" in store.caches
    assert len(store.caches["smithery:slack"].plugins) == 1


def test_plugin_info_strips_whitespace() -> None:
    p = MCPPluginInfo(name="  slack  ", description="  desc  ")
    assert p.name == "slack"
    assert p.description == "desc"


def test_plugin_info_forbids_extra() -> None:
    import pytest
    with pytest.raises(Exception):
        MCPPluginInfo(name="test", unknown_field="bad")
