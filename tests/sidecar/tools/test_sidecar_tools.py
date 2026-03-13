"""Backward-compat shim — tests have been split into domain-specific files.

The original tests that lived here now live in:
  - test_review_tools.py  — sidecar_scan / sidecar_status / sidecar_review / sidecar_acknowledge
  - test_map_tools.py     — sidecar_map / sidecar_map_view
  - test_task_tools.py    — sidecar_tasks / sidecar_task_update / sidecar_task_create
  - test_rule_tools.py    — sidecar_add_rule

New tools are covered by:
  - test_sidecar_fix.py      — sidecar_fix
  - test_sidecar_init.py     — sidecar_init
  - test_sidecar_activity.py — sidecar_activity
  - test_changelog_tools.py  — changelog_list / changelog_get

This file is intentionally empty so that pytest discovers the split files instead.
"""
