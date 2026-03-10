"""Skills Marketplace tab — browse and install from claude-plugins.dev."""
import streamlit as st

from cmdop_claude import Client


def render_marketplace(client: Client) -> None:
    """Browse and install skills from claude-plugins.dev registry."""
    st.markdown("### 🌐 Skills Marketplace")
    st.caption("Source: [claude-plugins.dev](https://claude-plugins.dev/skills) — 52k+ community skills")

    col_search, col_source = st.columns([4, 1])
    with col_search:
        query = st.text_input(
            "Search skills",
            placeholder="e.g. commit, review, refactor...",
            key="marketplace_query",
            label_visibility="collapsed",
        )
    with col_source:
        st.caption(f"📡 {client.registry.source_names[0]}")

    page_key = "marketplace_offset"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    prev_query_key = "_marketplace_prev_query"
    if st.session_state.get(prev_query_key) != query:
        st.session_state[page_key] = 0
        st.session_state[prev_query_key] = query

    offset: int = st.session_state[page_key]
    limit = 100

    with st.spinner("Loading skills..."):
        page = client.registry.search(query=query, limit=limit, offset=offset)

    if not page.skills:
        st.info("No skills found. Try a different search term.")
        return

    st.caption(f"Showing {offset + 1}–{min(offset + len(page.skills), page.total)} of {page.total:,} skills")

    for skill in page.skills:
        with st.container(border=True):
            col_info, col_action = st.columns([5, 1])
            with col_info:
                st.markdown(f"**{skill.display_name}**" + (f" `v{skill.version}`" if skill.version else ""))
                if skill.description:
                    st.caption(skill.description[:200] + ("…" if len(skill.description) > 200 else ""))
                meta_parts = []
                if skill.author:
                    meta_parts.append(f"👤 {skill.author}")
                if skill.stars:
                    meta_parts.append(f"⭐ {skill.stars}")
                if skill.installs:
                    meta_parts.append(f"⬇️ {skill.installs:,}")
                if meta_parts:
                    st.caption("  ·  ".join(meta_parts))
            with col_action:
                already = client.registry.is_installed(skill)
                if already:
                    st.success("Installed", icon="✅")
                else:
                    if st.button("Install", key=f"install_{skill.id}", type="primary"):
                        try:
                            name = client.registry.install(skill)
                            st.success(f"Installed as `{name}`")
                            st.rerun()
                        except FileExistsError:
                            st.warning("Already installed.")
                        except Exception as e:
                            st.error(str(e))

    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if offset > 0:
            if st.button("← Previous", key="marketplace_prev"):
                st.session_state[page_key] = max(0, offset - limit)
                st.rerun()
    with col_page:
        current_page = offset // limit + 1
        total_pages = (page.total + limit - 1) // limit
        st.caption(f"Page {current_page} of {total_pages}")
    with col_next:
        if offset + limit < page.total:
            if st.button("Next →", key="marketplace_next"):
                st.session_state[page_key] = offset + limit
                st.rerun()
