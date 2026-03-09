"""Skill Studio — installed, marketplace, and import tabs."""
import streamlit as st

from cmdop_claude import Client

from ._installed import render_installed
from ._marketplace import render_marketplace
from ._import import render_import


def render_skills(client: Client) -> None:
    """Render the Skill Studio."""
    st.header("Skill Studio")
    st.markdown("Manage independent capabilities that Claude can invoke dynamically.")

    tab_installed, tab_marketplace, tab_import = st.tabs(["📚 Installed", "🌐 Marketplace", "📥 Import"])

    with tab_installed:
        render_installed(client)

    with tab_marketplace:
        render_marketplace(client)

    with tab_import:
        render_import(client)


__all__ = ["render_skills"]
