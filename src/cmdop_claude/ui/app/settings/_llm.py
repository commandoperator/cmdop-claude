"""LLM provider routing configuration tab."""
import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude.models.config.cmdop_config import CmdopConfig, _LLM_ROUTING_DEFAULTS

_MODE_LABELS = {
    "openrouter": "OpenRouter — 300+ models (recommended)",
    "openai": "OpenAI — GPT-4o, o3",
    "sdkrouter": "SDKRouter — Internal",
}


def render_llm_routing() -> None:
    st.subheader("LLM Provider")
    cfg = CmdopConfig.load()
    routing = cfg.llm_routing

    mode_options = list(_LLM_ROUTING_DEFAULTS.keys())
    current_idx = mode_options.index(routing.mode) if routing.mode in mode_options else 0

    selected_mode = st.selectbox(
        "Provider",
        options=mode_options,
        index=current_idx,
        format_func=lambda m: _MODE_LABELS.get(m, m),
        key="llm_routing_mode",
    )

    info = _LLM_ROUTING_DEFAULTS[selected_mode]
    st.caption(f"API key URL: [{info['key_url']}]({info['key_url']}) | Env var: `{info['env_var']}`")

    current_key = routing.api_key if routing.mode == selected_mode else ""
    new_key = st.text_input(
        "API Key",
        value=current_key,
        type="password",
        placeholder=f"Paste your {selected_mode} API key here",
        key="llm_routing_key",
    )

    default_model = info["model"]
    current_model = routing.model if routing.mode == selected_mode else ""
    new_model = st.text_input(
        "Model override (optional)",
        value=current_model,
        placeholder=f"Default: {default_model}",
        key="llm_routing_model",
    )

    if ui.button("Save LLM Routing", key="btn_save_llm_routing"):
        if not new_key:
            st.warning("API key is required.")
        else:
            cfg.set_llm_routing(selected_mode, new_key, new_model)
            st.success(f"Saved. Provider: {selected_mode} | Model: {new_model or default_model}")
            st.rerun()
