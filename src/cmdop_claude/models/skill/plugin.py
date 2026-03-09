"""MCP Plugin registry models."""
from datetime import datetime, timezone
from typing import Literal, Optional

from cmdop_claude.models.base import CoreModel


class MCPToolInfo(CoreModel):
    """A single tool exposed by an MCP plugin."""
    name: str
    description: str = ""


class MCPPluginInfo(CoreModel):
    """Metadata for a discoverable MCP plugin."""
    name: str
    qualified_name: str = ""
    description: str = ""
    version: str = ""
    install_command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    remote_url: str = ""
    tools: list[MCPToolInfo] = []
    install_count: int = 0
    source: Literal["smithery", "official"] = "official"
    homepage_url: str = ""


class PluginCache(CoreModel):
    """Cached search results for a single query."""
    fetched_at: str = ""
    ttl_seconds: int = 3600
    plugins: list[MCPPluginInfo] = []
    query: str = ""

    def is_expired(self) -> bool:
        if not self.fetched_at:
            return True
        try:
            fetched = datetime.fromisoformat(self.fetched_at)
            now = datetime.now(timezone.utc)
            return (now - fetched).total_seconds() > self.ttl_seconds
        except Exception:
            return True


class PluginCacheStore(CoreModel):
    """All cached plugin queries, keyed by '{source}:{query}'."""
    caches: dict[str, PluginCache] = {}
