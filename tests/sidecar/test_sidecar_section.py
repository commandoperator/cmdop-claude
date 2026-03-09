"""Tests for inject_sidecar_workflow."""
import pytest

from cmdop_claude.sidecar._sidecar_section import inject_sidecar_workflow


def test_replaces_existing_workflow_section():
    content = "# MyProject\n\n## Workflow\n\n- old stuff\n- more old stuff\n\n## Key Rules\n\n- rule1\n"
    result = inject_sidecar_workflow(content)
    assert "sidecar_tasks" in result
    assert "old stuff" not in result
    assert "## Key Rules" in result


def test_inserts_before_key_rules_when_no_workflow():
    content = "# MyProject\n\n## Architecture\n\n- some dirs\n\n## Key Rules\n\n- rule1\n"
    result = inject_sidecar_workflow(content)
    assert "## Workflow" in result
    assert "sidecar_tasks" in result
    workflow_pos = result.index("## Workflow")
    key_rules_pos = result.index("## Key Rules")
    assert workflow_pos < key_rules_pos


def test_appends_when_no_workflow_and_no_key_rules():
    content = "# MyProject\n\n## Tech Stack\n\n- Python\n"
    result = inject_sidecar_workflow(content)
    assert "## Workflow" in result
    assert "sidecar_tasks" in result


def test_includes_docs_hint_when_provided():
    content = "# MyProject\n\n## Workflow\n\n- placeholder\n"
    result = inject_sidecar_workflow(content, docs_workflow_hint="Use docs_search to find guides in: Django docs.")
    assert "Django docs" in result


def test_no_docs_hint_when_empty():
    content = "# MyProject\n\n## Workflow\n\n- placeholder\n"
    result = inject_sidecar_workflow(content, docs_workflow_hint="")
    assert "Django docs" not in result
    assert "sidecar_tasks" in result


def test_includes_packages_hint_when_provided():
    content = "# MyProject\n\n## Workflow\n\n- placeholder\n"
    result = inject_sidecar_workflow(content, packages_hint="Package docs via DjangoCFG packages.")
    assert "DjangoCFG packages" in result
    assert "docs_reindex" in result


def test_idempotent_on_already_injected():
    content = "# MyProject\n\n## Workflow\n\n- old\n"
    result1 = inject_sidecar_workflow(content)
    result2 = inject_sidecar_workflow(result1)
    # Should not duplicate the section
    assert result2.count("## Workflow") == 1
    assert result2.count("sidecar_tasks") >= 1
