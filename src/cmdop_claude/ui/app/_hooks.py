"""Hooks Manager tab."""
import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude import Client


def render_hooks(client: Client) -> None:
    """Render the Hooks Management Studio."""
    st.header("Hooks Management Studio")
    st.markdown("Deterministically enforce guardrails via pre and post tool hooks.")

    hooks = client.hooks.list_hooks()

    if not hooks:
        st.info("No hooks found in the `.claude/hooks` directory.")
        return

    for name, hook in hooks.items():
        with st.container(border=True):
            st.subheader(f"🪝 {name}.json")
            st.write("---")

            tab_cfg, tab_editor = st.tabs(["⚙️ Configuration", "📝 Script Editor"])

            with tab_cfg:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Events (Triggers)**")
                    st.code(", ".join(hook.events))
                with col2:
                    st.markdown("**Target Script**")
                    st.code(hook.script)
                    if hook.args:
                        st.markdown("**Arguments**")
                        st.code(" ".join(hook.args))

            with tab_editor:
                current_script = client.hooks.get_hook_script(hook.script)
                if current_script:
                    new_script = st.text_area("Shell Script", value=current_script, height=200, key=f"script_{name}")
                    if ui.button("Save Script", key=f"btn_save_script_{name}"):
                        try:
                            client.hooks.update_hook_script(hook.script, new_script)
                            st.success("Script updated successfully!", icon="✅")
                        except Exception as e:
                            st.error(f"Failed to update script: {e}")
                else:
                    st.error(f"Target script not found: {hook.script}", icon="🚨")
