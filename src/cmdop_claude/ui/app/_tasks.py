"""Task Queue tab."""
import streamlit as st
import streamlit_shadcn_ui as ui
from streamlit_extras.metric_cards import style_metric_cards

from cmdop_claude import Client


def render_task_queue(client: Client) -> None:
    """Render the Task Queue tab."""
    st.header("Task Queue")
    st.markdown("Structured tasks from sidecar reviews and manual entries.")

    with st.expander("➕ Create New Task"):
        with st.form("create_task_form"):
            t_title = st.text_input("Title")
            t_desc = st.text_area("Description (markdown)")
            t_priority = st.selectbox("Priority", ["medium", "high", "critical", "low"])
            t_files = st.text_input("Context Files (comma separated)")
            submitted = st.form_submit_button("Create Task")
            if submitted and t_title and t_desc:
                try:
                    files = [f.strip() for f in t_files.split(",") if f.strip()] if t_files else None
                    task = client.sidecar.create_task(
                        title=t_title,
                        description=t_desc,
                        priority=t_priority,
                        context_files=files,
                    )
                    st.success(f"Created task {task.id}: {task.title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create task: {e}")

    st.write("---")

    status_filter = st.selectbox(
        "Filter by status",
        ["all", "pending", "in_progress", "completed", "dismissed"],
        key="task_status_filter",
    )

    tasks = client.sidecar.list_tasks(
        status=status_filter if status_filter != "all" else None
    )

    if not tasks:
        st.info("No tasks found.")
        return

    t1, t2, t3, t4 = st.columns(4)
    all_tasks = client.sidecar.list_tasks()
    pending_count = sum(1 for t in all_tasks if t.status == "pending")
    in_progress_count = sum(1 for t in all_tasks if t.status == "in_progress")
    completed_count = sum(1 for t in all_tasks if t.status == "completed")
    with t1:
        st.metric("Total", len(all_tasks))
    with t2:
        st.metric("Pending", pending_count)
    with t3:
        st.metric("In Progress", in_progress_count)
    with t4:
        st.metric("Completed", completed_count)

    style_metric_cards(
        background_color="#1E1E1E",
        border_left_color="#F59E0B",
        border_radius_px=8,
    )

    st.write("---")

    priority_colors = {
        "critical": "#FF4B4B",
        "high": "#F59E0B",
        "medium": "#3B82F6",
        "low": "#6B7280",
    }

    for task in tasks:
        color = priority_colors.get(task.priority, "#6B7280")
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f"<span style='color:{color};font-weight:bold;'>[{task.priority}]</span> "
                    f"**{task.title}** <small>(id: {task.id}, status: {task.status})</small>",
                    unsafe_allow_html=True,
                )
                if task.context_files:
                    st.caption(f"Files: {', '.join(task.context_files)}")
                with st.expander("Description"):
                    st.markdown(task.description)

            with col_actions:
                if task.status == "pending":
                    if ui.button("Start", key=f"btn_start_{task.id}"):
                        client.sidecar.update_task_status(task.id, "in_progress")
                        st.rerun()
                    if ui.button("Dismiss", key=f"btn_dismiss_{task.id}"):
                        client.sidecar.update_task_status(task.id, "dismissed")
                        st.rerun()
                elif task.status == "in_progress":
                    if ui.button("Complete", key=f"btn_complete_{task.id}"):
                        client.sidecar.update_task_status(task.id, "completed")
                        st.rerun()
