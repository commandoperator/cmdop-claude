"""Claude settings.json editor (project / user / local)."""
import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude import Client
from cmdop_claude.models.config.mcp import ClaudeSettings


def render_claude_settings(client: Client) -> None:
    tab_p, tab_u, tab_l = st.tabs(["📁 Project", "👤 User", "💻 Local"])

    with tab_p:
        st.subheader("Project Settings")
        st.markdown("`.claude/settings.json` — Shared with the team.")
        settings = client.mcp.get_settings("project")
        new_json = st.text_area("JSON Configuration", value=settings.model_dump_json(indent=2), height=200, key="settings_p")
        if ui.button("Save Project Settings", key="btn_save_settings_p"):
            try:
                client.mcp.write_settings(ClaudeSettings.model_validate_json(new_json), "project")
                st.success("Project settings saved!")
            except Exception as e:
                st.error(f"Invalid JSON: {e}")

    with tab_u:
        st.subheader("Global User Settings")
        st.markdown("`~/.claude/settings.json` — Your personal defaults.")
        settings = client.mcp.get_settings("user")
        new_json = st.text_area("JSON Configuration", value=settings.model_dump_json(indent=2), height=200, key="settings_u")
        if ui.button("Save User Settings", key="btn_save_settings_u"):
            try:
                client.mcp.write_settings(ClaudeSettings.model_validate_json(new_json), "user")
                st.success("User settings saved!")
            except Exception as e:
                st.error(f"Invalid JSON: {e}")

    with tab_l:
        st.subheader("Local Overrides")
        st.markdown("`.claude/settings.local.json` — Ignored by Git.")
        settings = client.mcp.get_settings("local")
        new_json = st.text_area("JSON Configuration", value=settings.model_dump_json(indent=2), height=200, key="settings_l")
        if ui.button("Save Local Settings", key="btn_save_settings_l"):
            try:
                client.mcp.write_settings(ClaudeSettings.model_validate_json(new_json), "local")
                st.success("Local settings saved!")
            except Exception as e:
                st.error(f"Invalid JSON: {e}")
