"""Changelog viewer tab — browsable release history."""
import streamlit as st

from cmdop_claude import Client


def render_changelog(client: Client) -> None:
    current_version: str | None = None
    try:
        import importlib.metadata
        current_version = importlib.metadata.version("cmdop-claude")
    except Exception:
        pass

    entries = client.changelog.list_entries(limit=50)
    if not entries:
        st.info("No changelog entries found. Run `/commit` to generate them.")
        return

    latest = entries[0]

    # Header bar
    col_ver, col_info = st.columns([1, 3])
    with col_ver:
        label = f"v{current_version}" if current_version else "Current version"
        st.metric(label, f"v{latest.version}")
    with col_info:
        st.markdown(f"**{latest.title}**")
        if latest.release_date:
            st.caption(latest.release_date.isoformat())

    st.divider()

    # Version selector
    version_labels = [f"v{e.version} — {e.title}" for e in entries]
    selected_idx = st.selectbox(
        "Select version",
        options=range(len(entries)),
        format_func=lambda i: version_labels[i],
        index=0,
        label_visibility="collapsed",
    )

    selected = entries[selected_idx]
    is_current = current_version and selected.version == current_version
    badge = " 🟢 current" if is_current else ""

    st.markdown(f"## v{selected.version} — {selected.title}{badge}")
    if selected.release_date:
        st.caption(f"Released {selected.release_date.isoformat()}")
    st.markdown(selected.content)
