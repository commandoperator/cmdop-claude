"""LLM provider routing configuration tab."""
import os
from typing import Any

import httpx
import streamlit as st
import streamlit_shadcn_ui as ui
from pydantic import BaseModel, ConfigDict

from cmdop_claude.models.config.cmdop_config import CmdopConfig, LLMRouting, _LLM_ROUTING_DEFAULTS


class _ModelInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""

    @property
    def label(self) -> str:
        return self.name if self.name and self.name != self.id else self.id

_MODE_LABELS = {
    "openrouter": "OpenRouter — 300+ models (recommended)",
    "openai": "OpenAI — GPT-4o, o3",
    "sdkrouter": "SDKRouter — Internal",
}

_ENV_VARS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "sdkrouter": "SDKROUTER_API_KEY",
}


def _fetch_models(routing: LLMRouting, key: str) -> list[_ModelInfo]:
    """Fetch available models from provider /models endpoint.

    Cached per (mode, key[:8]) in st.session_state to avoid repeated calls.
    Returns empty list on any error — caller falls back to text_input.
    """
    cache_key = f"_llm_models_{routing.mode}_{key[:8] if key else 'nokey'}"
    if cache_key in st.session_state:
        cached: list[_ModelInfo] = st.session_state[cache_key]
        return cached

    url = routing.resolved_base_url.rstrip("/") + "/models"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=8)
        r.raise_for_status()
        raw: Any = r.json()
        # OpenAI-compatible: {"data": [...]} or just [...]
        items: list[Any] = raw.get("data", raw) if isinstance(raw, dict) else raw
        models = [_ModelInfo.model_validate(m) for m in items if isinstance(m, dict) and "id" in m]
        models.sort(key=lambda m: m.id)
        st.session_state[cache_key] = models
        return models
    except Exception:
        return []


def _mask_key(key: str) -> str:
    if not key:
        return "—"
    if len(key) <= 8:
        return "●" * len(key)
    return key[:4] + "●" * (len(key) - 8) + key[-4:]


def _detect_key_source(routing: LLMRouting) -> tuple[str, str]:
    """Returns (source_label, key_value). source: 'config' | 'env' | 'none'."""
    env_var = _ENV_VARS.get(routing.mode, "")
    env_val = os.getenv(env_var, "")
    if env_val:
        return "env", env_val
    if routing.api_key:
        return "config", routing.api_key
    return "none", ""


def _test_connection(routing: LLMRouting, key: str) -> tuple[bool, str]:
    """Send a minimal request to verify the key works."""
    import httpx
    url = routing.resolved_base_url.rstrip("/") + "/models"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=8)
        if r.status_code in (200, 404):
            # 404 on /models is still a valid auth response for some providers
            return True, f"OK (HTTP {r.status_code})"
        if r.status_code == 401:
            return False, "Invalid API key (401 Unauthorized)"
        return False, f"Unexpected response: HTTP {r.status_code}"
    except httpx.TimeoutException:
        return False, "Timeout — server did not respond in 8s"
    except Exception as e:
        return False, str(e)


def render_llm_routing() -> None:
    cfg = CmdopConfig.load()
    routing = cfg.llm_routing

    # ── Current status banner ─────────────────────────────────────────────────
    source, active_key = _detect_key_source(routing)
    with st.container(border=True):
        col_mode, col_key, col_src = st.columns([2, 3, 2])
        with col_mode:
            st.markdown("**Provider**")
            st.markdown(f"`{routing.mode}`")
        with col_key:
            st.markdown("**Active key**")
            st.markdown(f"`{_mask_key(active_key)}`" if active_key else "⚠️ *not set*")
        with col_src:
            st.markdown("**Source**")
            if source == "env":
                st.success(f"env `{_ENV_VARS.get(routing.mode, '')}`")
            elif source == "config":
                st.info("config.json")
            else:
                st.warning("not configured")

        if active_key:
            if st.button("🔌 Test connection", key="btn_test_conn"):
                with st.spinner("Testing…"):
                    ok, msg = _test_connection(routing, active_key)
                if ok:
                    st.success(f"Connection OK — {msg}")
                else:
                    st.error(f"Failed — {msg}")

    st.divider()

    # ── Provider selector ─────────────────────────────────────────────────────
    st.subheader("Configure Provider")

    mode_options = list(_LLM_ROUTING_DEFAULTS.keys())
    current_idx = mode_options.index(routing.mode) if routing.mode in mode_options else 0

    selected_mode: str = st.selectbox(  # type: ignore[assignment]
        "Provider",
        options=mode_options,
        index=current_idx,
        format_func=lambda m: _MODE_LABELS.get(m) or m,
        key="llm_routing_mode",
    ) or mode_options[0]

    info = _LLM_ROUTING_DEFAULTS[selected_mode]
    env_var = _ENV_VARS.get(selected_mode, "SDKROUTER_API_KEY") or "SDKROUTER_API_KEY"

    col_info, col_env = st.columns([3, 2])
    with col_info:
        st.caption(f"Get your key: [{info['key_url']}]({info['key_url']})")
    with col_env:
        env_active = os.getenv(env_var, "")
        if env_active:
            st.caption(f"✅ `{env_var}` set in environment")
        else:
            st.caption(f"Env var: `{env_var}` *(not set)*")

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

    # Fetch models list — show selectbox if available, text_input as fallback
    fetch_key = new_key or os.getenv(env_var, "")
    models = _fetch_models(
        LLMRouting.model_validate({"mode": selected_mode, "apiKey": fetch_key}),
        fetch_key,
    ) if fetch_key else []

    if models:
        model_ids = [m.id for m in models]
        # Insert current/default at top if not in list
        for seed in (current_model, default_model):
            if seed and seed not in model_ids:
                model_ids.insert(0, seed)
        try:
            sel_idx = model_ids.index(current_model) if current_model in model_ids else model_ids.index(default_model)
        except ValueError:
            sel_idx = 0
        new_model: str = st.selectbox(  # type: ignore[assignment]
            "Model",
            options=model_ids,
            index=sel_idx,
            key="llm_routing_model",
            help=f"Default for this provider: {default_model}",
        ) or default_model
    else:
        new_model = st.text_input(
            "Model override (optional)",
            value=current_model,
            placeholder=f"Default: {default_model}",
            key="llm_routing_model",
            help="Set API key and click 'Test now' to load model list",
        )

    col_save, col_test = st.columns([2, 1])
    with col_save:
        if ui.button("Save", key="btn_save_llm_routing"):
            if not new_key and not env_active:
                st.warning("Provide an API key or set the env var.")
            else:
                cfg.set_llm_routing(selected_mode, new_key, new_model)
                st.success(f"Saved. Provider: {selected_mode} | Model: {new_model or default_model}")
                st.rerun()
    with col_test:
        test_key = new_key or env_active
        if test_key and st.button("Test now", key="btn_test_new"):
            # Temporarily build routing for selected mode to get correct base_url
            tmp = LLMRouting.model_validate({"mode": selected_mode, "apiKey": test_key})
            with st.spinner("Testing…"):
                ok, msg = _test_connection(tmp, test_key)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.divider()

    # ── Additional keys ───────────────────────────────────────────────────────
    st.subheader("Additional Keys")

    smithery_env = os.getenv("CLAUDE_CP_SMITHERY_API_KEY", "")
    smithery_cfg = cfg.smithery_api_key

    with st.container(border=True):
        st.markdown("**Smithery Registry** *(optional — enables plugin browser)*")
        smithery_active = smithery_env or smithery_cfg
        if smithery_active:
            src = "env `CLAUDE_CP_SMITHERY_API_KEY`" if smithery_env else "config.json"
            st.caption(f"Key set ({src}): `{_mask_key(smithery_active)}`")
        else:
            st.caption("Not set — plugin browser uses public API only (rate-limited)")

        new_smithery = st.text_input(
            "Smithery API Key",
            value=smithery_cfg,
            type="password",
            placeholder="sk-smithery-...",
            key="smithery_key_input",
        )
        if ui.button("Save Smithery Key", key="btn_save_smithery"):
            object.__setattr__(cfg, "smithery_api_key", new_smithery)
            cfg.save()
            st.success("Smithery key saved.")
            st.rerun()

    st.divider()

    # ── Environment overview ──────────────────────────────────────────────────
    with st.expander("Environment variable status"):
        rows = [
            ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "")),
            ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "")),
            ("SDKROUTER_API_KEY", os.getenv("SDKROUTER_API_KEY", "")),
            ("CLAUDE_CP_SMITHERY_API_KEY", os.getenv("CLAUDE_CP_SMITHERY_API_KEY", "")),
            ("CLAUDE_CP_SIDECAR_MODEL", os.getenv("CLAUDE_CP_SIDECAR_MODEL", "")),
            ("CMDOP_DEBUG_MODE", os.getenv("CMDOP_DEBUG_MODE", "")),
        ]
        for var, val in rows:
            col_v, col_s = st.columns([3, 1])
            with col_v:
                st.code(var)
            with col_s:
                if val:
                    st.success("set")
                else:
                    st.caption("—")
