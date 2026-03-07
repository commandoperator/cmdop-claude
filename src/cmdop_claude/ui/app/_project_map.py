"""Project Map tab."""
import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude import Client


def render_project_map(client: Client) -> None:
    """Render the Project Map tab."""
    st.header("Project Map")
    st.markdown("Auto-generated navigable project structure with LLM annotations.")

    col_gen, col_refresh = st.columns(2)
    with col_gen:
        if ui.button("Generate / Update Map", key="btn_map_gen"):
            with st.spinner("Generating project map..."):
                try:
                    result = client.sidecar.generate_map()
                    st.success(
                        f"Map updated: {len(result.directories)} dirs, "
                        f"{len(result.entry_points)} entry points "
                        f"({result.tokens_used} tokens, {result.model_used})"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Map generation failed: {e}")
    with col_refresh:
        if ui.button("Refresh View", key="btn_map_refresh"):
            st.rerun()

    st.write("---")

    map_content = client.sidecar.get_current_map()
    if map_content:
        st.markdown(map_content)
    else:
        st.info("No project map yet. Click 'Generate / Update Map' to create one.")
