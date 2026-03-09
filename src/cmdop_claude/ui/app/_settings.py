"""Settings & Security tab."""
import streamlit as st

from cmdop_claude import Client
from cmdop_claude.ui.app.settings import render_llm_routing, render_claude_settings, render_guardrails


def render_settings(client: Client) -> None:
    st.header("Settings & Security")

    tab_llm, tab_claude, tab_guard = st.tabs(["🤖 LLM Provider", "⚙️ Claude Settings", "🛡️ Guardrails"])

    with tab_llm:
        render_llm_routing()

    with tab_claude:
        render_claude_settings(client)

    with tab_guard:
        render_guardrails(client)
