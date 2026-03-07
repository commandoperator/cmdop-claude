"""Sidecar Monitor tab."""
from pathlib import Path

import streamlit as st
import streamlit_shadcn_ui as ui
from streamlit_extras.metric_cards import style_metric_cards

from cmdop_claude import Client


def render_sidecar(client: Client) -> None:
    """Render the Sidecar Monitor tab."""
    st.header("Sidecar Monitor")
    st.markdown("Documentation librarian — finds staleness, contradictions, and gaps in `.claude/` files.")

    status = client.sidecar.get_status()

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Last Scan", status.last_run.strftime("%Y-%m-%d") if status.last_run else "Never")
    with s2:
        st.metric("Pending Items", status.pending_items)
    with s3:
        st.metric("Suppressed", status.suppressed_items)
    with s4:
        st.metric("Tokens Today", status.tokens_today)

    style_metric_cards(
        background_color="#1E1E1E",
        border_left_color="#8B5CF6",
        border_radius_px=8,
    )

    mcp_registered = client.sidecar.is_mcp_registered()
    st.write("---")
    mcp_col1, mcp_col2 = st.columns([3, 1])
    with mcp_col1:
        if mcp_registered:
            st.success("MCP server registered in .mcp.json")
        else:
            st.warning("MCP server not registered — Claude cannot call sidecar tools")
    with mcp_col2:
        if mcp_registered:
            if ui.button("Unregister MCP", key="btn_mcp_unreg"):
                client.sidecar.unregister_mcp()
                st.rerun()
        else:
            if ui.button("Register MCP", key="btn_mcp_reg"):
                client.sidecar.register_mcp()
                st.rerun()

    st.write("---")

    col_scan, col_status = st.columns(2)
    with col_scan:
        if ui.button("Run Scan Now", key="btn_sidecar_scan"):
            with st.spinner("Scanning documentation..."):
                try:
                    result = client.sidecar.generate_review()
                    st.success(f"Review generated: {len(result.items)} items found ({result.tokens_used} tokens)")
                    st.rerun()
                except RuntimeError as e:
                    st.warning(f"Skipped: {e}")
                except Exception as e:
                    st.error(f"Scan failed: {e}")

    with col_status:
        if ui.button("Refresh Status", key="btn_sidecar_refresh"):
            st.rerun()

    st.write("---")

    sidecar_dir = Path(client._config.claude_dir_path) / ".sidecar"
    review_path = sidecar_dir / "review.md"

    if review_path.exists():
        st.subheader("Current Review")
        review_text = review_path.read_text(encoding="utf-8")
        st.markdown(review_text)

        st.write("---")
        st.subheader("Manage Items")
        st.markdown("Suppress an item by entering its ID (shown in parentheses in the review).")
        with st.form("acknowledge_form"):
            ack_id = st.text_input("Item ID to suppress")
            ack_days = st.number_input("Suppress for N days", min_value=1, max_value=365, value=30)
            if st.form_submit_button("Suppress"):
                if ack_id:
                    client.sidecar.acknowledge(ack_id, int(ack_days))
                    st.success(f"Suppressed {ack_id} for {ack_days} days")
    else:
        st.info("No review yet. Click 'Run Scan Now' to generate the first review.")

    history_dir = sidecar_dir / "history"
    if history_dir.exists():
        history_files = sorted(history_dir.glob("*.md"), reverse=True)
        if history_files:
            st.write("---")
            with st.expander("Past Reviews"):
                for hf in history_files[:10]:
                    st.markdown(f"**{hf.stem}**")
                    st.text(hf.read_text(encoding="utf-8")[:500])
                    st.write("---")
