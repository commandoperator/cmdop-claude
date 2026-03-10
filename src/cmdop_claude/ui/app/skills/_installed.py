"""Installed skills tab — compact list with detail panel."""
import subprocess

import markdown
import streamlit as st
import streamlit_shadcn_ui as ui
from markdownify import markdownify
from streamlit_jodit import st_jodit  # type: ignore[import]

from cmdop_claude import Client
from cmdop_claude.models.skill.skill import SkillFrontmatter


def render_installed(client: Client) -> None:
    # ── Create new ───────────────────────────────────────────────────────
    with st.expander("➕ Create New Skill"):
        with st.form("create_skill_form"):
            new_name = st.text_input("Skill name (kebab-case, e.g. code-reviewer)")
            new_desc = st.text_input("Description")
            if st.form_submit_button("Create"):
                if new_name:
                    try:
                        client.skills.create_skill(new_name, new_desc)
                        st.success(f"Created '{new_name}'", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("Name is required.")

    # ── Skill list ───────────────────────────────────────────────────────
    skills: dict[str, SkillFrontmatter] = client.skills.list_skills()
    if not skills:
        st.info("No skills found in `~/.claude/skills/`.")
        return

    query = st.text_input("🔍 Filter", placeholder="Search by name or description...", key="skills_filter", label_visibility="collapsed")
    if query:
        skills = client.skills.search_skills(query)
        if not skills:
            st.info(f"No skills matching '{query}'.")
            return

    selected = st.session_state.get("selected_skill")
    if selected and selected not in skills:
        selected = None
        st.session_state["selected_skill"] = None

    # Two-column layout: list | detail
    col_list, col_detail = st.columns([1, 2], gap="medium")

    with col_list:
        st.caption(f"{len(skills)} skill{'s' if len(skills) != 1 else ''}")
        for name, skill in skills.items():  # skill: SkillFrontmatter
            label = skill.name or name
            is_active = selected == name
            badge = "🟢 " if not skill.disable_model_invocation else "⚪ "
            if st.button(
                f"{badge}{label}",
                key=f"sel_{name}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["selected_skill"] = name
                st.rerun()

    with col_detail:
        if not selected:
            st.info("← Select a skill to view details")
        else:
            name = selected
            skill = skills[name]
            _render_skill_detail(client, name, skill)


def _render_skill_detail(client: Client, name: str, skill: SkillFrontmatter) -> None:
    col_title, col_delete = st.columns([4, 1])
    with col_title:
        st.subheader(f"✨ {skill.name or name}")
        if skill.description:
            st.caption(skill.description[:200])
    with col_delete:
        if st.button("🗑️ Delete", key=f"del_{name}", type="secondary"):
            st.session_state[f"confirm_delete_{name}"] = True

    if st.session_state.get(f"confirm_delete_{name}"):
        st.warning(f"Delete **{name}**? This cannot be undone.")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, delete", key=f"del_confirm_{name}", type="primary"):
                try:
                    client.skills.delete_skill(name)
                    st.session_state["selected_skill"] = None
                    st.session_state[f"confirm_delete_{name}"] = False
                    st.success(f"Deleted '{name}'")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with col_no:
            if st.button("Cancel", key=f"del_cancel_{name}"):
                st.session_state[f"confirm_delete_{name}"] = False
                st.rerun()
        return

    tab_settings, tab_editor = st.tabs(["⚙️ Settings", "📝 Prompt Editor"])

    with tab_settings:
        col1, col2 = st.columns(2)
        with col1:
            is_manual = ui.switch(
                default_checked=skill.disable_model_invocation,
                label="Manual only (disable auto-invoke)",
                key=f"switch_{name}",
            )
            allowed_tools = st.multiselect(
                "Allowed Tools",
                options=skill.allowed_tools,
                default=skill.allowed_tools,
                key=f"tools_{name}",
                accept_new_options=True,
            )
        with col2:
            st.markdown("**Actions**")
            if ui.button("Save Settings", key=f"btn_save_{name}"):
                skill.disable_model_invocation = is_manual
                skill.allowed_tools = allowed_tools
                try:
                    client.skills.update_skill(name, skill)
                    st.success("Saved", icon="✅")
                except Exception as e:
                    st.error(str(e))
            if st.button("📂 Open Folder", key=f"btn_reveal_{name}"):
                try:
                    subprocess.run(["open", str(client.skills.get_skill_dir_path(name))], check=True)
                except Exception as e:
                    st.error(str(e))

    with tab_editor:
        current_content = client.skills.get_skill_content(name)
        is_dark = st.session_state.get("theme", "dark") == "dark"
        jodit_config: dict[str, object] = {
            "height": 420,
            "theme": "dark" if is_dark else "default",
        }
        if is_dark:
            jodit_config["style"] = {"background": "#0e1117", "color": "#fafafa"}

        new_html = st_jodit(
            value=markdown.markdown(current_content),
            config=jodit_config,
            key=f"editor_{name}",
        )
        if ui.button("Save Prompt", key=f"btn_save_content_{name}"):
            try:
                if new_html:
                    new_md = markdownify(new_html, heading_style="ATX", strip=["p"]).strip()
                    client.skills.update_skill_content(name, new_md)
                    st.success("Saved", icon="✅")
            except Exception as e:
                st.error(str(e))
