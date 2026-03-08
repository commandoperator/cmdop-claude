"""Tests for TOON serialization."""
import pytest

from cmdop_claude.sidecar.toon import paths_to_tree, to_grouped_prefix_blocks, to_toon


# ── to_toon ──────────────────────────────────────────────────────────


def test_to_toon_nested_dirs() -> None:
    tree = {
        "src": {
            "services": {
                "git.py": None,
                "map.py": None,
            },
            "__init__.py": None,
        },
        "tests": {
            "conftest.py": None,
        },
    }
    result = to_toon(tree)
    lines = result.splitlines()

    # Dirs come before files at each level; dirs sorted alphabetically
    assert lines[0] == "src/"
    assert lines[-1].endswith("conftest.py")

    # Indentation: nested items have 2-space prefix
    assert any(line.startswith("  ") for line in lines)
    assert any(line.startswith("    ") for line in lines)


def test_to_toon_dirs_before_files() -> None:
    tree = {
        "z_file.py": None,
        "a_dir": {"child.py": None},
    }
    result = to_toon(tree)
    lines = result.splitlines()
    assert lines[0] == "a_dir/"
    assert lines[-1] == "z_file.py"


def test_to_toon_empty_dir() -> None:
    tree: dict = {}
    assert to_toon(tree) == ""


def test_to_toon_empty_nested_dir() -> None:
    tree = {"empty_dir": {}}
    result = to_toon(tree)
    assert result == "empty_dir/"


def test_to_toon_single_file() -> None:
    tree = {"README.md": None}
    assert to_toon(tree) == "README.md"


def test_to_toon_indent_levels() -> None:
    tree = {"a": {"b": {"c.py": None}}}
    result = to_toon(tree)
    assert "a/" in result
    assert "  b/" in result
    assert "    c.py" in result


# ── paths_to_tree ─────────────────────────────────────────────────────


def test_paths_to_tree_flat_files() -> None:
    paths = ["README.md", "setup.py", "pyproject.toml"]
    tree = paths_to_tree(paths)
    assert tree == {"README.md": None, "setup.py": None, "pyproject.toml": None}


def test_paths_to_tree_nested_paths() -> None:
    paths = ["src/main.py", "src/utils.py", "tests/test_main.py"]
    tree = paths_to_tree(paths)
    assert "src" in tree
    assert isinstance(tree["src"], dict)
    assert tree["src"]["main.py"] is None
    assert tree["src"]["utils.py"] is None
    assert tree["tests"]["test_main.py"] is None


def test_paths_to_tree_directory_paths() -> None:
    paths = ["src/", "tests/"]
    tree = paths_to_tree(paths)
    assert tree["src"] == {}
    assert tree["tests"] == {}


def test_paths_to_tree_mixed() -> None:
    paths = ["src/", "src/main.py", "README.md"]
    tree = paths_to_tree(paths)
    assert isinstance(tree["src"], dict)
    assert tree["src"]["main.py"] is None
    assert tree["README.md"] is None


def test_paths_to_tree_deep_nesting() -> None:
    paths = ["a/b/c/deep.py"]
    tree = paths_to_tree(paths)
    assert isinstance(tree["a"], dict)
    assert isinstance(tree["a"]["b"], dict)
    assert isinstance(tree["a"]["b"]["c"], dict)
    assert tree["a"]["b"]["c"]["deep.py"] is None


# ── to_grouped_prefix_blocks ──────────────────────────────────────────


def test_to_grouped_prefix_blocks_basic() -> None:
    paths = [
        "src/services/git.py",
        "src/services/map.py",
        "src/services/review.py",
        "tests/conftest.py",
        "tests/test_git.py",
    ]
    result = to_grouped_prefix_blocks(paths)
    assert "[src/services]" in result
    assert "git.py" in result
    assert "map.py" in result
    assert "[tests]" in result
    assert "conftest.py" in result


def test_to_grouped_prefix_blocks_root_files() -> None:
    paths = ["README.md", "setup.py", "src/main.py"]
    result = to_grouped_prefix_blocks(paths)
    assert "[.]" in result
    assert "README.md" in result
    assert "setup.py" in result
    assert "[src]" in result


def test_to_grouped_prefix_blocks_files_space_separated() -> None:
    paths = ["pkg/a.py", "pkg/b.py", "pkg/c.py"]
    result = to_grouped_prefix_blocks(paths)
    block_lines = result.splitlines()
    # Header line + file line
    assert len(block_lines) == 2
    file_line = block_lines[1]
    assert "a.py" in file_line
    assert "b.py" in file_line
    assert "c.py" in file_line
    # Files are separated by spaces (two spaces)
    assert "  " in file_line


def test_to_grouped_prefix_blocks_sorted_groups() -> None:
    paths = ["z_dir/z.py", "a_dir/a.py"]
    result = to_grouped_prefix_blocks(paths)
    a_pos = result.index("[a_dir]")
    z_pos = result.index("[z_dir]")
    assert a_pos < z_pos


def test_to_grouped_prefix_blocks_empty() -> None:
    assert to_grouped_prefix_blocks([]) == ""


# ── round-trip ────────────────────────────────────────────────────────


def test_roundtrip_paths_to_toon() -> None:
    paths = [
        "src/__init__.py",
        "src/main.py",
        "src/services/git.py",
        "src/services/map.py",
        "tests/conftest.py",
        "tests/test_main.py",
    ]
    tree = paths_to_tree(paths)
    result = to_toon(tree)
    lines = result.splitlines()

    # Top-level dirs come first (sorted)
    assert lines[0] == "src/"
    # src files are indented
    assert "  __init__.py" in lines
    assert "  main.py" in lines
    # Nested dir
    assert "  services/" in lines
    # Doubly indented
    assert "    git.py" in lines
    assert "    map.py" in lines
    # tests block
    assert "tests/" in lines
    assert "  conftest.py" in lines


# ── token efficiency ──────────────────────────────────────────────────


def test_toon_shorter_than_comma_joined() -> None:
    paths = [
        "src/services/git.py",
        "src/services/map.py",
        "src/services/review.py",
        "src/models/base.py",
        "src/models/user.py",
        "tests/conftest.py",
        "tests/test_git.py",
        "tests/test_map.py",
    ]
    tree = paths_to_tree(paths)
    toon_output = to_toon(tree)
    comma_joined = ", ".join(paths)

    assert len(toon_output) < len(comma_joined), (
        f"TOON ({len(toon_output)} chars) should be shorter than "
        f"comma-joined ({len(comma_joined)} chars)"
    )
