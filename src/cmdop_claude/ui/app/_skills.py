"""Skill Studio tab."""
import subprocess

import streamlit as st
import streamlit_shadcn_ui as ui
from streamlit_extras.stoggle import stoggle
from streamlit_jodit import st_jodit
import markdown
from markdownify import markdownify

from cmdop_claude import Client


def render_skills(client: Client) -> None:
    """Render the Skill Studio."""
    st.header("Skill Studio")
    st.markdown("Manage independent capabilities that Claude can invoke dynamically.")

    tab_installed, tab_import = st.tabs(["📚 Installed", "📥 Import"])

    with tab_installed:
        _render_installed(client)

    with tab_import:
        _render_import(client)


def _render_installed(client: Client) -> None:
    with st.expander("➕ Create New Skill"):
        with st.form("create_skill_form"):
            new_name = st.text_input("Skill Name (e.g., Code Reviewer)")
            new_desc = st.text_input("Description (helps Claude know when to use it)")
            submitted = st.form_submit_button("Provision Skill")
            if submitted:
                if new_name:
                    try:
                        client.skills.create_skill(new_name, new_desc)
                        st.success(f"Skill '{new_name}' created successfully!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create skill: {e}")
                else:
                    st.error("Name is required.")

    st.write("---")
    st.markdown("### 📚 Quick Start Templates")
    st.markdown("Scaffold production-grade community templates in one click.")
    col_t1, col_t2, col_t3 = st.columns(3)
    try:
        with col_t1:
            if ui.button("Code Reviewer", key="btn_tpl_cr"):
                client.skills.create_skill("code_reviewer", "Deep PR review for TypeScript and error handling")
                client.skills.update_skill_content("code_reviewer", "# Code Reviewer\n1. Validate strict types\n2. Check test coverage\n3. Review for obvious security flags")
                st.rerun()
        with col_t2:
            if ui.button("Test Generator", key="btn_tpl_tg"):
                client.skills.create_skill("test_gen", "Outputs TDD tests based on requirement specs")
                client.skills.update_skill_content("test_gen", "# Test Gen\nWhen asked to write a test:\n1. Use pytest or jest\n2. Cover edge cases")
                st.rerun()
        with col_t3:
            if ui.button("Refactoring", key="btn_tpl_ref"):
                client.skills.create_skill("refactor_expert", "Breaks down complex functions safely")
                client.skills.update_skill_content("refactor_expert", "# Refactor Expert\nRules:\n1. Never change business logic\n2. Use pure functions where possible")
                st.rerun()
    except Exception as e:
        st.error(f"Failed to scaffold: {e}")

    st.write("---")

    skills = client.skills.list_skills()

    if not skills:
        st.info("No skills found in the `.claude/skills` directory.")
        return

    query = st.text_input("🔍 Filter skills", placeholder="Search by name or description...", key="skills_filter")
    if query:
        skills = client.skills.search_skills(query)
        if not skills:
            st.info(f"No skills matching '{query}'.")
            return

    for name, skill in skills.items():
        with st.container(border=True):
            st.subheader(f"✨ {skill.name or name}")

            if skill.description:
                stoggle("View Skill Description", skill.description)

            st.write("---")

            tab_settings, tab_editor = st.tabs(["⚙️ Settings", "📝 Prompt Editor"])

            with tab_settings:
                col1, col2, col3 = st.columns([1, 2, 2])

                with col1:
                    st.markdown("**Auto-Activation**")
                    is_manual = ui.switch(default_checked=skill.disable_model_invocation, label="Manual Only", key=f"switch_{name}")

                with col2:
                    st.markdown("**Allowed Tools**")
                    allowed_tools = st.multiselect("Select Tools", options=["Read", "Write", "Bash"], default=skill.allowed_tools, key=f"tools_{name}", label_visibility="collapsed")

                with col3:
                    st.markdown("**Actions**")
                    col_save, col_open = st.columns(2)
                    with col_save:
                        if ui.button("Save Settings", key=f"btn_save_{name}"):
                            skill.disable_model_invocation = is_manual
                            skill.allowed_tools = allowed_tools
                            try:
                                client.skills.update_skill(name, skill)
                                st.success("Updated successfully!", icon="✅")
                            except Exception as e:
                                st.error(f"Failed to update {name}: {e}")
                    with col_open:
                        if st.button("📂 Reveal Folder", key=f"btn_reveal_{name}"):
                            folder_path = client.skills.get_skill_dir_path(name)
                            try:
                                subprocess.run(['open', str(folder_path)], check=True)
                            except Exception as e:
                                st.error(f"Could not open folder: {e}")

            with tab_editor:
                current_content = client.skills.get_skill_content(name)

                st.markdown("### Markdown Instructions")

                is_dark = st.session_state.get('theme', 'dark') == 'dark'

                if is_dark:
                    st.markdown("""
                        <style>
                        iframe[title="streamlit_jodit.st_jodit"] {
                            color-scheme: dark;
                        }
                        </style>
                        """, unsafe_allow_html=True)

                html_content = markdown.markdown(current_content)

                jodit_config = {
                    "height": 500,
                    "theme": "dark" if is_dark else "default",
                }

                if is_dark:
                    jodit_config["style"] = {
                        "background": "#0e1117",
                        "color": "#fafafa"
                    }
                    jodit_config["toolbarButtonSize"] = "middle"

                new_html = st_jodit(
                    value=html_content,
                    config=jodit_config,
                    key=f"editor_{name}"
                )

                if ui.button("Save Prompt", key=f"btn_save_content_{name}"):
                    try:
                        if new_html:
                            new_markdown = markdownify(new_html, heading_style="ATX", strip=['p']).strip()
                            client.skills.update_skill_content(name, new_markdown)
                            st.success("Prompt instructions saved!", icon="✅")
                    except Exception as e:
                        st.error(f"Failed to save content: {e}")


def _render_import(client: Client) -> None:
    st.markdown("### Import Skill from Local Path")
    st.markdown("Copy a skill folder into `~/.claude/skills/`. The folder must contain a `SKILL.md` file.")

    with st.form("import_skill_form"):
        src_path = st.text_input(
            "Skill folder path",
            placeholder="/path/to/my-skill  or  ~/projects/skills/pdf",
        )
        submitted = st.form_submit_button("Preview & Import")

        if submitted and src_path:
            try:
                name = client.skills.import_from_path(src_path.strip())
                st.success(f"Skill **{name}** imported successfully!", icon="✅")
                st.rerun()
            except FileExistsError as e:
                st.warning(str(e))
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Import failed: {e}")

    st.write("---")
    st.markdown("### Community Skills")
    st.info(
        "Browse and install skills from the community registry — coming soon.\n\n"
        "In the meantime: [github.com/commandoperator/cmdop-skills](https://github.com/commandoperator)"
    )
