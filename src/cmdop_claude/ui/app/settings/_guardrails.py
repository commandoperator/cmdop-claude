"""Guardrails (permissions) tab."""
import streamlit as st
import streamlit_shadcn_ui as ui

from cmdop_claude import Client


def render_guardrails(client: Client) -> None:
    perms = client.claude.get_permissions()
    if not perms:
        st.info("No `.permissions.json` found.")
        return

    st.markdown("Control what tools Claude can run globally without confirmation.")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("📁 File Operations")
            read_op = ui.switch(default_checked=perms.allowed_operations.file_operations.read, label="Read", key="sw_read")
            create_op = ui.switch(default_checked=perms.allowed_operations.file_operations.create, label="Create", key="sw_create")
            edit_op = ui.switch(default_checked=perms.allowed_operations.file_operations.edit, label="Edit", key="sw_edit")
            delete_op = ui.switch(default_checked=perms.allowed_operations.file_operations.delete, label="Delete", key="sw_delete")
    with col2:
        with st.container(border=True):
            st.subheader("🛡️ System & Execution")
            run_scripts_op = ui.switch(default_checked=perms.allowed_operations.code_execution.run_scripts, label="Run Scripts", key="sw_run_scripts")
            run_tests_op = ui.switch(default_checked=perms.allowed_operations.code_execution.run_tests, label="Run Tests", key="sw_run_tests")
            install_op = ui.switch(default_checked=perms.allowed_operations.system_operations.install_packages, label="Install Packages", key="sw_install")
            sudo_op = ui.switch(default_checked=perms.allowed_operations.system_operations.run_as_sudo, label="Run as Sudo", key="sw_sudo")

    if ui.button("Save Guardrails", key="btn_save_perms"):
        perms.allowed_operations.file_operations.read = read_op
        perms.allowed_operations.file_operations.create = create_op
        perms.allowed_operations.file_operations.edit = edit_op
        perms.allowed_operations.file_operations.delete = delete_op
        perms.allowed_operations.code_execution.run_scripts = run_scripts_op
        perms.allowed_operations.code_execution.run_tests = run_tests_op
        perms.allowed_operations.system_operations.install_packages = install_op
        perms.allowed_operations.system_operations.run_as_sudo = sudo_op
        try:
            client.claude.write_permissions(perms)
            st.success("Guardrails saved!")
        except Exception as e:
            st.error(f"Failed: {e}")
