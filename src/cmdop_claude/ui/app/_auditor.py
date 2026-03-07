"""Health Auditor tab."""
from pathlib import Path

import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from cmdop_claude import Client


def render_auditor(client: Client) -> None:
    """Render the Context Health Auditor with smarter metrics."""
    stats = client.get_project_dashboard_stats()

    col_title, col_score = st.columns([3, 1])
    with col_title:
        st.header(f"🚀 {stats.project_name}")
        st.markdown(f"**Cognitive Intelligence Board** — Deep audit of your `.claude` environment.")

    with col_score:
        color = "#4BFF4B" if stats.health_score > 80 else "#FFA500" if stats.health_score > 50 else "#FF4B4B"
        st.markdown(f"""
            <div style="text-align: right; padding: 10px; border-radius: 10px; background: #1E1E1E; border-right: 5px solid {color};">
                <div style="font-size: 0.8rem; color: #888;">HEALTH SCORE</div>
                <div style="font-size: 2rem; font-weight: bold; color: {color};">{int(stats.health_score)}%</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("---")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Context Weight", f"{stats.claude_md_lines} L", delta="Lines" if stats.claude_md_lines < 50 else "High Load", delta_color="normal" if stats.claude_md_lines < 50 else "inverse")
    with m2:
        st.metric("Skill Library", f"{stats.skill_count}", delta="Modular")
    with m3:
        st.metric("MCP Servers", f"{stats.mcp_count}", delta="Connected")
    with m4:
        st.metric("Hook Hooks", f"{stats.hook_count}", delta="Active")

    style_metric_cards(
        background_color="#1E1E1E",
        border_left_color="#3B82F6",
        border_radius_px=8
    )

    st.write("---")

    col_status, col_recs = st.columns([1, 1])

    with col_status:
        st.subheader("🛠️ Environment Status")
        if stats.health_score > 80:
            st.success("Claude environment is highly optimized and modular.", icon="✨")
        elif stats.health_score > 50:
            st.warning("Environment is functional but could benefit from refactoring.", icon="⚠️")
        else:
            st.error("Severe cognitive load detected. Project performance may degrade.", icon="🚨")

        with st.container(border=True):
            st.markdown("**Active Components**")
            st.write(f"📂 **Project Path:** `{Path('.').absolute()}`")
            st.write(f"🧠 **Primary Memory:** `CLAUDE.md` ({stats.claude_md_lines} lines)")
            st.write(f"🧬 **Skills Registry:** {stats.skill_count} active workflows")
            st.write(f"🔗 **Event Hooks:** {stats.hook_count} configured triggers")

    with col_recs:
        st.subheader("💡 Smart Recommendations")
        if not stats.recommendations:
            st.markdown("No urgent actions needed. Your project structure is elite. 🏆")
        else:
            for rec in stats.recommendations:
                st.info(rec, icon="💡")
