"""Service for browsing, installing, and managing MCP plugins from registries."""
import json
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cmdop_claude._config import Config
from cmdop_claude.models.config.mcp import MCPConfig, MCPServerCommand, MCPServerURL
from cmdop_claude.models.skill.plugin import (
    MCPPluginInfo,
    MCPToolInfo,
    PluginCache,
    PluginCacheStore,
)
from cmdop_claude.services.base import BaseService

logger = logging.getLogger(__name__)

_SMITHERY_API = "https://registry.smithery.ai/servers"
_OFFICIAL_API = "https://registry.modelcontextprotocol.io/v0/servers"

# Cache key for the full Official index
_OFFICIAL_INDEX_KEY = "official:__index__"


class PluginService(BaseService):
    """Browse, install, and manage MCP plugins from Smithery and Official registries."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        # Global cache — MCP plugins install to ~/.claude.json, not per-project
        cache_path = config.plugins_cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path = cache_path
        self._index_lock = threading.Lock()
        self._index_thread: Optional[threading.Thread] = None
        # Start background index fetch if cache is missing or expired
        self._maybe_start_index_fetch()

    def _maybe_start_index_fetch(self) -> None:
        """Start background thread to fetch Official registry index if needed."""
        cached = self._get_cached(_OFFICIAL_INDEX_KEY)
        if cached is not None:
            return
        self._index_thread = threading.Thread(
            target=self._fetch_official_index, daemon=True
        )
        self._index_thread.start()

    def _fetch_official_index(self) -> None:
        """Fetch all pages from Official registry and cache as full index."""
        try:
            all_plugins: list[MCPPluginInfo] = []
            cursor = ""
            for _ in range(10):
                url = f"{_OFFICIAL_API}?limit=100"
                if cursor:
                    url += f"&cursor={urllib.request.quote(cursor)}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                page = self._normalize_official(data)
                all_plugins.extend(page)
                metadata = data.get("metadata", {})
                cursor = metadata.get("nextCursor", "")
                if not cursor or len(page) < 100:
                    break

            with self._index_lock:
                self._set_cached(_OFFICIAL_INDEX_KEY, "", all_plugins)
            logger.info("Official registry index cached: %d plugins", len(all_plugins))
        except Exception as e:
            logger.warning("Background index fetch failed: %s", e)

    # ── Public API ───────────────────────────────────────────────────

    def search(self, query: str = "", source: str = "all") -> list[MCPPluginInfo]:
        """Search both registries and return merged results."""
        results: list[MCPPluginInfo] = []
        if source in ("all", "smithery"):
            results.extend(self.search_smithery(query))
        if source in ("all", "official"):
            results.extend(self.search_official(query))
        return results

    def search_smithery(self, query: str = "") -> list[MCPPluginInfo]:
        """Search the Smithery registry. Requires smithery_api_key in config."""
        cache_key = f"smithery:{query}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        api_key = self._config.smithery_api_key
        if not api_key:
            return []

        try:
            url = f"{_SMITHERY_API}?q={urllib.request.quote(query)}&pageSize=20"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        plugins = self._normalize_smithery(data)
        self._set_cached(cache_key, query, plugins)
        return plugins

    def is_index_building(self) -> bool:
        """Return True if the background index fetch is still running."""
        return self._index_thread is not None and self._index_thread.is_alive()

    def search_official(self, query: str = "") -> list[MCPPluginInfo]:
        """Search the Official MCP registry using the cached index.

        The Official API doesn't support server-side search. We maintain a
        full index in background and filter client-side. If the index isn't
        ready yet, wait up to 30s for it to complete.
        """
        # Try the full cached index first
        with self._index_lock:
            index = self._get_cached(_OFFICIAL_INDEX_KEY)

        if index is not None:
            return self._filter_plugins(index, query)

        # Index not ready — wait for background thread to finish
        if self._index_thread and self._index_thread.is_alive():
            self._index_thread.join(timeout=30.0)
            with self._index_lock:
                index = self._get_cached(_OFFICIAL_INDEX_KEY)
            if index is not None:
                return self._filter_plugins(index, query)

        # Thread finished but no cache (fetch failed) — try 1 page as fallback
        try:
            url = f"{_OFFICIAL_API}?limit=100"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            plugins = self._normalize_official(data)
            return self._filter_plugins(plugins, query)
        except Exception:
            return []

    @staticmethod
    def _filter_plugins(
        plugins: list[MCPPluginInfo], query: str, limit: int = 20
    ) -> list[MCPPluginInfo]:
        """Filter and deduplicate plugins by query string."""
        if query:
            q = query.lower()
            plugins = [
                p for p in plugins
                if q in p.name.lower() or q in p.description.lower()
            ]
        # Deduplicate by name, keeping the first occurrence (latest version)
        seen: dict[str, MCPPluginInfo] = {}
        for p in plugins:
            if p.name not in seen:
                seen[p.name] = p
        return list(seen.values())[:limit]

    _INTERNAL_SERVERS = {"sidecar"}

    def _claude_json_path(self) -> Path:
        return Path.home() / ".claude.json"

    def _read_claude_json(self) -> MCPConfig:
        path = self._claude_json_path()
        if not path.exists():
            return MCPConfig()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return MCPConfig.model_validate(data)
        except Exception:
            return MCPConfig()

    def _write_claude_json(self, config: MCPConfig) -> None:
        path = self._claude_json_path()
        data = config.model_dump(mode="json")
        # Clean up server entries: remove defaults for cleaner JSON
        for srv in data.get("mcpServers", {}).values():
            if isinstance(srv, dict):
                if srv.get("type") == "command":
                    srv.pop("type", None)
                if not srv.get("env"):
                    srv.pop("env", None)
                if not srv.get("args"):
                    srv.pop("args", None)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_installed_names(self) -> set[str]:
        """Return set of MCP server names in ~/.claude.json, excluding internal servers."""
        config = self._read_claude_json()
        return set(config.mcpServers.keys()) - self._INTERNAL_SERVERS

    def install_plugin(self, plugin: MCPPluginInfo) -> bool:
        """Install a plugin by writing its config to ~/.claude.json mcpServers.
        Returns True if added, False if already exists.
        """
        config = self._read_claude_json()
        if plugin.name in config.mcpServers:
            return False

        if plugin.remote_url:
            server = MCPServerURL(url=plugin.remote_url, env=plugin.env)
        else:
            server = MCPServerCommand(
                command=plugin.install_command or "npx",
                args=plugin.args,
                env=plugin.env,
            )

        config.mcpServers[plugin.name] = server
        self._write_claude_json(config)
        return True

    def uninstall_plugin(self, name: str) -> bool:
        """Remove a plugin from ~/.claude.json mcpServers.
        Returns True if removed, False if not found.
        """
        config = self._read_claude_json()
        if name not in config.mcpServers:
            return False

        del config.mcpServers[name]
        self._write_claude_json(config)
        return True

    def clear_cache(self) -> None:
        """Clear all cached plugin data and re-trigger background index fetch."""
        if self._cache_path.exists():
            self._cache_path.unlink()
        self._maybe_start_index_fetch()

    # ── Cache helpers ────────────────────────────────────────────────

    def _load_store(self) -> PluginCacheStore:
        if not self._cache_path.exists():
            return PluginCacheStore()
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return PluginCacheStore.model_validate(data)
        except Exception:
            return PluginCacheStore()

    def _save_store(self, store: PluginCacheStore) -> None:
        self._cache_path.write_text(
            store.model_dump_json(indent=2), encoding="utf-8"
        )

    def _get_cached(self, cache_key: str) -> Optional[list[MCPPluginInfo]]:
        store = self._load_store()
        cache = store.caches.get(cache_key)
        if cache and not cache.is_expired():
            return cache.plugins
        return None

    def _set_cached(self, cache_key: str, query: str, plugins: list[MCPPluginInfo]) -> None:
        store = self._load_store()
        store.caches[cache_key] = PluginCache(
            fetched_at=datetime.now(timezone.utc).isoformat(),
            plugins=plugins,
            query=query,
        )
        self._save_store(store)

    # ── Normalization ────────────────────────────────────────────────

    def _normalize_smithery(self, data: dict) -> list[MCPPluginInfo]:
        """Normalize Smithery API response to MCPPluginInfo list."""
        plugins: list[MCPPluginInfo] = []
        servers = data.get("servers", data.get("results", []))
        if isinstance(servers, list):
            for srv in servers:
                tools = []
                for t in srv.get("tools", []):
                    tools.append(MCPToolInfo(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                    ))
                plugins.append(MCPPluginInfo(
                    name=srv.get("displayName", srv.get("name", "")),
                    qualified_name=srv.get("qualifiedName", srv.get("name", "")),
                    description=srv.get("description", ""),
                    version=srv.get("version", ""),
                    install_command=srv.get("installCommand", "npx"),
                    args=srv.get("args", []),
                    env=srv.get("env", {}),
                    tools=tools,
                    install_count=srv.get("useCount", srv.get("installCount", 0)),
                    source="smithery",
                    homepage_url=srv.get("homepage", ""),
                ))
        return plugins

    def _normalize_official(self, data: dict) -> list[MCPPluginInfo]:
        """Normalize Official MCP registry response to MCPPluginInfo list.

        Official API wraps each entry as {"server": {...}, "_meta": {...}}.
        """
        plugins: list[MCPPluginInfo] = []
        servers = data.get("servers", data.get("results", []))
        if isinstance(servers, list):
            for entry in servers:
                # Unwrap nested "server" key if present
                srv = entry.get("server", entry) if isinstance(entry, dict) else entry
                if not isinstance(srv, dict):
                    continue

                tools = []
                for t in srv.get("tools", []):
                    tools.append(MCPToolInfo(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                    ))

                # Extract remote URL (streamable-http) if available
                remote_url = ""
                remotes = srv.get("remotes", [])
                if isinstance(remotes, list):
                    for r in remotes:
                        if isinstance(r, dict) and r.get("url"):
                            remote_url = r["url"]
                            break

                # Build install command from packages if no remote
                install_cmd = ""
                args: list[str] = []
                if not remote_url:
                    install_cmd = "npx"
                    packages = srv.get("packages", [])
                    if packages and isinstance(packages, list):
                        pkg = packages[0] if packages else {}
                        if isinstance(pkg, dict):
                            install_cmd = pkg.get("runtime", "npx")
                            pkg_name = pkg.get("name", "")
                            if pkg_name:
                                args = ["-y", pkg_name]

                repo = srv.get("repository", {})
                repo_url = repo.get("url", "") if isinstance(repo, dict) else ""

                plugins.append(MCPPluginInfo(
                    name=srv.get("name", srv.get("title", "")),
                    qualified_name=srv.get("name", ""),
                    description=srv.get("description", ""),
                    version=srv.get("version", ""),
                    install_command=install_cmd,
                    args=args,
                    remote_url=remote_url,
                    tools=tools,
                    source="official",
                    homepage_url=srv.get("websiteUrl", repo_url),
                ))
        return plugins
