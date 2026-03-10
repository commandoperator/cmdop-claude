"""Streamlit dashboard — decomposed into logical modules."""
import streamlit as st
from streamlit_option_menu import option_menu

from cmdop_claude import Client

from ._auditor import render_auditor
from .skills import render_skills
from ._mcp import render_mcp_studio, render_plugin_browser
from ._docs import render_docs_browser
from ._hooks import render_hooks
from ._sidecar import render_sidecar
from ._project_map import render_project_map
from ._tasks import render_task_queue
from ._settings import render_settings
from ._graph import render_graph
from ._changelog import render_changelog

__all__ = [
    "main",
    "render_auditor",
    "render_skills",
    "render_mcp_studio",
    "render_plugin_browser",
    "render_docs_browser",
    "render_hooks",
    "render_sidecar",
    "render_project_map",
    "render_task_queue",
    "render_settings",
    "render_graph",
    "render_changelog",
]


def main() -> None:
    """Main application loop."""
    st.set_page_config(
        page_title="Claude Control Plane",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    client = Client()

    with st.sidebar:
        st.markdown("### 🤖 Command Center")
        selected = option_menu(
            menu_title=None,
            options=[
                # Overview
                "Overview",
                "Project Map",
                "Task Queue",
                "Changelog",
                # Content
                "Skills",
                "Plugins",
                "Docs",
                # Config
                "MCP",
                "Hooks",
                "Settings",
                # Dev
                "Sidecar",
                "Trigger Graph",
            ],
            icons=[
                # Overview
                "heart-pulse",
                "map",
                "list-task",
                "clock-history",
                # Content
                "stars",
                "puzzle",
                "book-half",
                # Config
                "box",
                "plug",
                "shield-lock",
                # Dev
                "activity",
                "diagram-3",
            ],
            menu_icon="cast",
            default_index=0,
            styles={
                "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#2c2c2c"},
                "nav-link-selected": {"background-color": "#FF4B4B"},
            }
        )

    _RENDERERS = {
        "Overview": render_auditor,
        "Project Map": render_project_map,
        "Task Queue": render_task_queue,
        "Changelog": render_changelog,
        "Skills": render_skills,
        "Plugins": render_plugin_browser,
        "Docs": render_docs_browser,
        "MCP": render_mcp_studio,
        "Hooks": render_hooks,
        "Settings": render_settings,
        "Sidecar": render_sidecar,
        "Trigger Graph": render_graph,
    }

    renderer = _RENDERERS.get(selected)
    if renderer:
        renderer(client)


if __name__ == "__main__":
    main()
