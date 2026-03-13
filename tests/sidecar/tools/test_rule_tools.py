"""Tests for sidecar_add_rule tool."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the shared service singleton between tests."""
    import cmdop_claude.sidecar.tools._service_registry as reg
    reg._service = None
    yield
    reg._service = None


@pytest.fixture()
def mock_svc():
    """Mock SidecarService so no real scanning or LLM calls happen."""
    with patch("cmdop_claude.sidecar.tools.init_tools.get_service") as mock_get:
        svc = MagicMock()
        mock_get.return_value = svc
        yield svc


def test_sidecar_add_rule_creates_file(mock_svc, tmp_path: Path) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_add_rule

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    mock_svc._claude_dir = claude_dir

    result = sidecar_add_rule(
        filename="python.md",
        content="# Python Rules\n\n- Use snake_case\n",
    )

    rule_path = claude_dir / "rules" / "python.md"
    assert rule_path.exists()
    assert "# Python Rules" in rule_path.read_text()
    assert "Created" in result
    assert "always loaded" in result


def test_sidecar_add_rule_with_paths(mock_svc, tmp_path: Path) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_add_rule

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    mock_svc._claude_dir = claude_dir

    result = sidecar_add_rule(
        filename="go.md",
        content="# Go Rules\n\n- Handle errors explicitly\n",
        paths=["**/*.go", "cmd/**/*.go"],
    )

    rule_path = claude_dir / "rules" / "go.md"
    content = rule_path.read_text()
    assert "---" in content
    assert "**/*.go" in content
    assert "# Go Rules" in content
    assert "lazy" in result
    assert "2 path pattern(s)" in result


def test_sidecar_add_rule_updates_existing(mock_svc, tmp_path: Path) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_add_rule

    claude_dir = tmp_path / ".claude"
    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "workflow.md").write_text("# Old content\n", encoding="utf-8")
    mock_svc._claude_dir = claude_dir

    result = sidecar_add_rule(
        filename="workflow.md",
        content="# New content\n\n- Updated rule\n",
    )

    assert "Updated" in result
    assert "New content" in (rules_dir / "workflow.md").read_text()


def test_sidecar_add_rule_adds_md_extension(mock_svc, tmp_path: Path) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_add_rule

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    mock_svc._claude_dir = claude_dir

    result = sidecar_add_rule(filename="testing", content="# Testing\n\n- Run pytest\n")

    rule_path = claude_dir / "rules" / "testing.md"
    assert rule_path.exists()
    assert "testing.md" in result


def test_sidecar_add_rule_preserves_existing_frontmatter(mock_svc, tmp_path: Path) -> None:
    from cmdop_claude.sidecar.tools.init_tools import sidecar_add_rule

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    mock_svc._claude_dir = claude_dir

    content_with_fm = '---\npaths:\n  - "**/*.py"\n---\n\n# Python\n\n- Rule\n'
    result = sidecar_add_rule(
        filename="python.md",
        content=content_with_fm,
        paths=["**/*.ts"],  # Should NOT override existing frontmatter
    )

    rule_path = claude_dir / "rules" / "python.md"
    written = rule_path.read_text()
    # Since content starts with ---, it should be used as-is
    assert written.startswith("---\npaths:\n  - \"**/*.py\"")
    assert "**/*.ts" not in written
