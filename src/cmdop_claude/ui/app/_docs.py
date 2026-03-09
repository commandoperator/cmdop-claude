"""Docs Browser tab — search and read bundled + custom documentation."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude import Client
from cmdop_claude.models.config.cmdop_config import CmdopConfig, DocsSource
from cmdop_claude.services.docs.docs_service import DocsService


def _load_config() -> CmdopConfig:
    return CmdopConfig.load()


def _save_sources(sources: list[DocsSource]) -> None:
    cfg = _load_config()
    object.__setattr__(cfg, "docs_sources", sources)
    cfg.save()


def _count_files(path: str) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return sum(1 for _ in p.rglob("*") if _.suffix in {".md", ".mdx"})


def render_docs_browser(client: Client) -> None:  # noqa: ARG001
    st.header("Docs Browser")
    st.markdown("Search and read documentation sources available to your agents via `docs_search` / `docs_get` MCP tools.")

    cfg = _load_config()
    svc = DocsService(cfg.docs_sources)

    tab_search, tab_sources = st.tabs(["Search", "Sources"])

    # ── Search tab ────────────────────────────────────────────────
    with tab_search:
        # File viewer — shown at top if a file is open
        if "docs_open_path" in st.session_state:
            path = st.session_state["docs_open_path"]
            rel = st.session_state.get("docs_open_rel", path)
            col_title, col_close = st.columns([5, 1])
            with col_title:
                st.subheader(rel)
            with col_close:
                if ui.button("← Back", key="btn_docs_close"):
                    del st.session_state["docs_open_path"]
                    del st.session_state["docs_open_rel"]
                    st.rerun()
            st.write("---")
            content = svc.get(path)
            st.markdown(content)
            st.stop()

        # Search bar
        col_q, col_btn = st.columns([5, 1])
        with col_q:
            query = st.text_input("Search docs", placeholder="e.g. migration, centrifugo, testing...")
        with col_btn:
            st.write("")
            st.write("")
            ui.button("Search", key="btn_docs_search")

        if query:
            # Search results
            results = svc.search(query, limit=20)
            if results:
                st.caption(f"{len(results)} result(s) for **{query}**")
                for i, r in enumerate(results):
                    rel = r["path"]
                    for root in cfg.docs_paths:
                        if r["path"].startswith(root):
                            rel = r["path"][len(root):].lstrip("/")
                            break
                    with st.container(border=True):
                        col_info, col_open = st.columns([5, 1])
                        with col_info:
                            st.markdown(f"**{rel}**")
                            st.caption(r["excerpt"][:160].strip())
                        with col_open:
                            if ui.button("Read", key=f"btn_docs_open_{i}"):
                                st.session_state["docs_open_path"] = r["path"]
                                st.session_state["docs_open_rel"] = rel
                                st.rerun()
            else:
                st.info(f"No results for **{query}**")
        else:
            # Default view — all docs grouped by source
            all_docs = svc.list_all()
            if not all_docs:
                st.info("No documentation files found. Add a source in the **Sources** tab.")
            else:
                st.caption(f"{len(all_docs)} document(s)")
                # Group by source
                by_source: dict[str, list[dict]] = {}
                for doc in all_docs:
                    src_label = doc["source"] or "unknown"
                    by_source.setdefault(src_label, []).append(doc)

                for src_label, docs in by_source.items():
                    with st.expander(f"**{src_label}** — {len(docs)} docs", expanded=True):
                        # Group by subdirectory
                        by_dir: dict[str, list[dict]] = {}
                        for doc in docs:
                            parts = doc["path"].split("/")
                            dir_name = "/".join(parts[:-1]) or "."
                            by_dir.setdefault(dir_name, []).append(doc)

                        for dir_name, dir_docs in sorted(by_dir.items()):
                            if dir_name != ".":
                                st.markdown(f"**{dir_name}/**")
                            for j, doc in enumerate(dir_docs):
                                col_name, col_btn2 = st.columns([5, 1])
                                with col_name:
                                    fname = doc["path"].split("/")[-1]
                                    title = doc["title"] or fname
                                    st.markdown(f"&nbsp;&nbsp;`{fname}` — {title}")
                                with col_btn2:
                                    if ui.button("Read", key=f"btn_default_open_{src_label}_{j}_{dir_name}"):
                                        st.session_state["docs_open_path"] = doc["path"]
                                        st.session_state["docs_open_rel"] = doc["path"]
                                        st.rerun()

    # ── Sources tab ───────────────────────────────────────────────
    with tab_sources:
        st.subheader("Configured sources")
        st.markdown("Stored in `~/.claude/cmdop/config.json` → `docsPaths`. Agents search all sources.")

        sources = list(cfg.docs_sources)

        for i, src in enumerate(sources):
            with st.container(border=True):
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    count = _count_files(src.path)
                    exists = Path(src.path).exists()
                    status = f"`{count} files`" if exists else "path not found"
                    label = src.description or src.path
                    st.markdown(f"**{label}** — {status}")
                    st.caption(src.path)
                with col_del:
                    if len(sources) > 1:  # keep at least one
                        if ui.button("Remove", key=f"btn_docs_rm_{i}"):
                            sources.pop(i)
                            _save_sources(sources)
                            st.rerun()

        st.write("---")
        with st.expander("Add documentation source"):
            with st.form("add_docs_source_form"):
                new_path = st.text_input("Path", placeholder="/absolute/path/to/docs")
                new_desc = st.text_input("Description", placeholder="My project docs — Django guides, API reference")
                submitted = st.form_submit_button("Add source")
                if submitted:
                    if not new_path:
                        st.error("Path is required.")
                    elif not Path(new_path).exists():
                        st.warning(f"Path does not exist: {new_path}. Added anyway.")
                        sources.append(DocsSource(path=new_path, description=new_desc))
                        _save_sources(sources)
                        st.rerun()
                    else:
                        sources.append(DocsSource(path=new_path, description=new_desc))
                        _save_sources(sources)
                        st.success(f"Added: {new_path}")
                        st.rerun()
