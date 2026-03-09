"""Import tab — copy local skill folder into ~/.claude/skills/."""
import streamlit as st

from cmdop_claude import Client


def render_import(client: Client) -> None:
    """Import a skill from a local path."""
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
