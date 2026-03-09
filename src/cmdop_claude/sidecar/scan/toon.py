"""TOON (Token-Oriented Object Notation) — compact directory tree serialization.

~60% fewer tokens than JSON for directory trees passed to LLMs.
"""
from __future__ import annotations


def to_toon(tree: dict, _indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * _indent

    dirs = sorted(k for k, v in tree.items() if isinstance(v, dict))
    files = sorted(k for k, v in tree.items() if v is None)

    for name in dirs:
        lines.append(f"{prefix}{name}/")
        child_block = to_toon(tree[name], _indent + 1)
        if child_block:
            lines.append(child_block)

    for name in files:
        lines.append(f"{prefix}{name}")

    return "\n".join(lines)


def paths_to_tree(paths: list[str]) -> dict:
    tree: dict = {}
    for path in paths:
        is_dir = path.endswith("/")
        parts = path.rstrip("/").split("/")
        node = tree
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if is_last:
                if is_dir:
                    node.setdefault(part, {})
                else:
                    node.setdefault(part, None)
            else:
                if part not in node or node[part] is None:
                    node[part] = {}
                node = node[part]
    return tree


def to_grouped_prefix_blocks(paths: list[str]) -> str:
    groups: dict[str, list[str]] = {}
    for path in paths:
        if "/" in path:
            slash = path.rfind("/")
            prefix = path[:slash]
            name = path[slash + 1:]
        else:
            prefix = ""
            name = path

        if not name:
            continue

        groups.setdefault(prefix, []).append(name)

    blocks: list[str] = []
    for prefix in sorted(groups.keys()):
        names = sorted(groups[prefix])
        header = f"[{prefix}]" if prefix else "[.]"
        blocks.append(f"{header}\n{'  '.join(names)}")

    return "\n\n".join(blocks)
