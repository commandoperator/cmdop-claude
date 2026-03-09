"""MCP Studio + Plugin Browser tab."""
import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude import Client
from cmdop_claude.models.config.mcp import MCPServerCommand, MCPServerURL, MCPServerConfig


def _format_server_config(cfg: MCPServerConfig) -> str:
    if isinstance(cfg, MCPServerURL):
        return f"url: {cfg.url}"
    return f"{cfg.command} {' '.join(cfg.args)}"


def render_mcp_studio(client: Client) -> None:
    """Render the MCP Server Studio."""
    st.header("MCP Server Studio")
    st.markdown("Orchestrate **Model Context Protocol** servers to extend Claude's capabilities.")

    col_g, col_p = st.columns(2)

    with col_g:
        st.subheader("🌍 Global Servers")
        st.markdown("`~/.claude.json`")
        global_cfg = client.mcp.get_global_mcp_config()
        if not global_cfg.mcpServers:
            st.info("No global MCP servers configured.")
        for name, cfg in global_cfg.mcpServers.items():
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.code(_format_server_config(cfg))

    with col_p:
        st.subheader("📁 Project Servers")
        st.markdown("`.mcp.json`")
        project_cfg = client.mcp.get_project_mcp_config()
        if not project_cfg.mcpServers:
            st.info("No project-level MCP servers.")
        for name, cfg in project_cfg.mcpServers.items():
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.code(_format_server_config(cfg))

    st.write("---")
    with st.expander("➕ Connect New MCP Server"):
        with st.form("add_mcp_form"):
            s_name = st.text_input("Server Name")
            s_cmd = st.text_input("Command (e.g. npx, python)")
            s_args = st.text_input("Arguments (space separated)")
            s_scope = st.selectbox("Scope", ["Project", "Global"])
            submitted = st.form_submit_button("Connect Server")
            if submitted and s_name and s_cmd:
                try:
                    from cmdop_claude.models.config.mcp import MCPServerCommand
                    new_srv = MCPServerCommand(command=s_cmd, args=s_args.split() if s_args else [])
                    if s_scope == "Project":
                        cfg = client.mcp.get_project_mcp_config()
                        cfg.mcpServers[s_name] = new_srv
                        client.mcp.write_project_mcp_config(cfg)
                    else:
                        cfg = client.mcp.get_global_mcp_config()
                        cfg.mcpServers[s_name] = new_srv
                        client.mcp.write_global_mcp_config(cfg)
                    st.success(f"Server {s_name} connected!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to connect: {e}")

def _render_plugin_card(
    plugin, idx: int, installed_names: set[str], client: Client, key_prefix: str
) -> None:
    """Render a single plugin card."""
    with st.container(border=True):
        col_info, col_action = st.columns([4, 1])
        with col_info:
            badge = " `INSTALLED`" if plugin.name in installed_names else ""
            source_badge = f"`{plugin.source}`"
            name_display = plugin.name
            if plugin.homepage_url:
                name_display = f"[{plugin.name}]({plugin.homepage_url})"
            st.markdown(f"**{name_display}** {source_badge}{badge}")
            if plugin.description:
                st.caption(plugin.description)

            meta_parts = []
            if plugin.version:
                meta_parts.append(f"v{plugin.version}")
            if plugin.install_count:
                meta_parts.append(f"{plugin.install_count:,} installs")
            if plugin.tools:
                meta_parts.append(f"{len(plugin.tools)} tools")
            if meta_parts:
                st.caption(" · ".join(meta_parts))

        with col_action:
            if plugin.name in installed_names:
                if ui.button("Uninstall", key=f"btn_{key_prefix}_uninstall_{idx}"):
                    client.plugins.uninstall_plugin(plugin.name)
                    st.rerun()
            else:
                if ui.button("Install", key=f"btn_{key_prefix}_install_{idx}"):
                    if client.plugins.install_plugin(plugin):
                        st.success(f"Installed {plugin.name}")
                    else:
                        st.warning(f"{plugin.name} already installed")
                    st.rerun()

        if plugin.tools:
            with st.expander("Tools", expanded=False):
                for t in plugin.tools:
                    desc = f" — {t.description}" if t.description else ""
                    st.markdown(f"- `{t.name}`{desc}")


def render_plugin_browser(client: Client) -> None:
    """Render the Plugin Browser as a standalone page."""
    st.header("Plugin Browser")
    st.markdown("Discover and install MCP plugins from **Smithery** and **Official** registries.")

    tab_installed, tab_search = st.tabs(["Installed", "Search"])

    installed_names = client.plugins.get_installed_names()

    # ── Installed tab ─────────────────────────────────────────────
    with tab_installed:
        if not installed_names:
            st.info("No plugins installed yet. Use the **Search** tab to find and install plugins.")
        else:
            st.caption(f"{len(installed_names)} installed plugin(s)")
            # Try to find plugin info from cache for richer display
            from cmdop_claude.services.plugins.plugin_service import _OFFICIAL_INDEX_KEY
            index = client.plugins._get_cached(_OFFICIAL_INDEX_KEY) or []
            index_map = {p.name: p for p in index}

            for idx, name in enumerate(sorted(installed_names)):
                plugin = index_map.get(name)
                if plugin:
                    _render_plugin_card(plugin, idx, installed_names, client, "inst")
                else:
                    # Minimal card for plugins not in index
                    with st.container(border=True):
                        col_info, col_action = st.columns([4, 1])
                        with col_info:
                            st.markdown(f"**{name}** `INSTALLED`")
                        with col_action:
                            if ui.button("Uninstall", key=f"btn_inst_uninstall_fallback_{idx}"):
                                client.plugins.uninstall_plugin(name)
                                st.rerun()

    # ── Search tab ────────────────────────────────────────────────
    with tab_search:
        col_search, col_filter, col_refresh = st.columns([3, 1, 1])
        with col_search:
            query = st.text_input("Search plugins", value="", key="plugin_search_q", placeholder="e.g. slack, filesystem, github...")
        with col_filter:
            source_filter = st.selectbox("Source", ["All", "Smithery", "Official"], key="plugin_source_filter")
        with col_refresh:
            st.write("")
            st.write("")
            refresh = ui.button("Refresh", key="btn_plugin_refresh")

        if refresh:
            client.plugins.clear_cache()

        source_map = {"All": "all", "Smithery": "smithery", "Official": "official"}
        source_val = source_map[source_filter]

        building = client.plugins.is_index_building()

        if query or refresh:
            spinner_msg = "Building plugin index (first time takes ~30s)..." if building else "Searching..."
            with st.spinner(spinner_msg):
                plugins = client.plugins.search(query=query, source=source_val)
        else:
            if building:
                st.caption("Building Official registry index in background...")
            plugins = []

        if plugins:
            st.caption(f"Found {len(plugins)} plugin(s)")
            for idx, plugin in enumerate(plugins):
                _render_plugin_card(plugin, idx, installed_names, client, "search")
        elif query:
            st.info("No plugins found. Try a different search term.")

        store = client.plugins._load_store()
        if store.caches:
            cached_count = len(store.caches)
            st.caption(f"Cache: {cached_count} cached quer{'y' if cached_count == 1 else 'ies'}")
