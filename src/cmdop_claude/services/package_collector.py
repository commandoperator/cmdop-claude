"""Collect raw source files from a single TypeScript package directory.

No LLM calls — pure filesystem. Returns CollectedPackage ready for synthesis.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Dirs always excluded regardless of config
_ALWAYS_SKIP = frozenset({
    "node_modules", "dist", ".venv", "__pycache__", ".git",
    "@sources", "@archive", "@vendor",
})

# Story file suffixes
_STORY_SUFFIXES = {".story.tsx", ".story.ts", ".story.jsx", ".story.js",
                   ".stories.tsx", ".stories.ts", ".stories.jsx", ".stories.js"}

# Max file size to read (bytes)
_MAX_FILE_SIZE = 100_000


@dataclass
class CollectedPackage:
    pkg_dir: str                              # "ui-core"
    package_name: str                         # "@djangocfg/ui-core"
    version: str                              # "1.0.0"
    readme: str                               # root README.md content
    sub_readmes: list[tuple[str, str]] = field(default_factory=list)  # (rel_path, content)
    export_lines: list[str] = field(default_factory=list)             # export { ... } lines
    stories: list[tuple[str, str]] = field(default_factory=list)      # (rel_path, content)
    fingerprint: str = ""


def _should_skip_dir(name: str, extra_exclude: list[str]) -> bool:
    return name in _ALWAYS_SKIP or name in extra_exclude or name.startswith(".")


def _read_safe(path: Path) -> str:
    """Read file, return empty string on error or if too large."""
    try:
        if path.stat().st_size > _MAX_FILE_SIZE:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_package_json(pkg_root: Path) -> tuple[str, str]:
    """Return (name, version) from package.json."""
    pj = pkg_root / "package.json"
    if not pj.exists():
        return pkg_root.name, "0.0.0"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        return data.get("name", pkg_root.name), data.get("version", "0.0.0")
    except Exception:
        return pkg_root.name, "0.0.0"


def _extract_export_lines(text: str) -> list[str]:
    """Pull export { ... } and export type { ... } lines from TS source."""
    lines = []
    # Multi-line export blocks: export {\n  Foo,\n  Bar\n} from '...'
    # We collapse them to single lines for simplicity
    collapsed = re.sub(r"\{\s*\n[\s\S]*?\}", lambda m: m.group(0).replace("\n", " "), text)
    for line in collapsed.splitlines():
        stripped = line.strip()
        if re.match(r"^export\s+(type\s+)?\{", stripped) or \
           re.match(r"^export\s+(default\s+)?(function|class|const|let|var|type|interface|enum)\s+\w", stripped):
            lines.append(stripped[:300])  # cap line length
    return lines


def _compute_fingerprint(pkg_root: Path, extra_exclude: list[str]) -> str:
    """SHA256[:16] of sorted (path, mtime, size) for tracked files."""
    parts: list[str] = []

    # README
    readme = pkg_root / "README.md"
    if readme.exists():
        s = readme.stat()
        parts.append(f"{readme}:{s.st_mtime:.0f}:{s.st_size}")

    # Stories + index files in src/
    src = pkg_root / "src"
    if src.is_dir():
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            # Check if any parent dir is excluded
            rel_parts = f.relative_to(src).parts
            if any(_should_skip_dir(p, extra_exclude) for p in rel_parts[:-1]):
                continue
            suffix_lower = "".join(f.suffixes).lower()
            is_story = any(suffix_lower.endswith(s) for s in _STORY_SUFFIXES)
            is_index = f.name == "index.ts" or f.name == "index.tsx"
            if is_story or is_index:
                s = f.stat()
                parts.append(f"{f}:{s.st_mtime:.0f}:{s.st_size}")

    parts.sort()
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def _collect_stories(src_dir: Path, extra_exclude: list[str]) -> list[tuple[str, str]]:
    """Recursively collect all story files, returning (rel_path, content)."""
    results: list[tuple[str, str]] = []
    for f in sorted(src_dir.rglob("*")):
        if not f.is_file():
            continue
        rel_parts = f.relative_to(src_dir).parts
        if any(_should_skip_dir(p, extra_exclude) for p in rel_parts[:-1]):
            continue
        suffix_lower = "".join(f.suffixes).lower()
        if not any(suffix_lower.endswith(s) for s in _STORY_SUFFIXES):
            continue
        content = _read_safe(f)
        if content:
            results.append((str(f.relative_to(src_dir)), content))
    return results


def _collect_export_lines(src_dir: Path, extra_exclude: list[str]) -> list[str]:
    """Collect export lines from src/index.ts and src/*/index.ts (depth ≤ 2)."""
    lines: list[str] = []
    # depth 1: src/index.ts
    for name in ("index.ts", "index.tsx"):
        p = src_dir / name
        if p.exists():
            lines.extend(_extract_export_lines(_read_safe(p)))

    # depth 2: src/<subdir>/index.ts
    try:
        for sub in sorted(src_dir.iterdir()):
            if not sub.is_dir():
                continue
            if _should_skip_dir(sub.name, extra_exclude):
                continue
            for name in ("index.ts", "index.tsx"):
                p = sub / name
                if p.exists():
                    lines.extend(_extract_export_lines(_read_safe(p)))
    except OSError:
        pass

    return lines


def _collect_sub_readmes(src_dir: Path, extra_exclude: list[str]) -> list[tuple[str, str]]:
    """Find README.md files inside src/, excluding dev/refactoring dirs."""
    results: list[tuple[str, str]] = []
    for f in sorted(src_dir.rglob("README.md")):
        rel_parts = f.relative_to(src_dir).parts
        if any(_should_skip_dir(p, extra_exclude) for p in rel_parts[:-1]):
            continue
        content = _read_safe(f)
        if content and len(content) > 10:  # skip near-empty files
            results.append((str(f.relative_to(src_dir)), content))
    return results


def collect(pkg_root: Path, extra_exclude: list[str] | None = None) -> CollectedPackage:
    """Collect all documentation sources from a single package directory."""
    exclude = list(extra_exclude or [])
    name, version = _parse_package_json(pkg_root)
    fingerprint = _compute_fingerprint(pkg_root, exclude)

    readme = _read_safe(pkg_root / "README.md")

    src = pkg_root / "src"
    stories: list[tuple[str, str]] = []
    export_lines: list[str] = []
    sub_readmes: list[tuple[str, str]] = []

    if src.is_dir():
        stories = _collect_stories(src, exclude)
        export_lines = _collect_export_lines(src, exclude)
        sub_readmes = _collect_sub_readmes(src, exclude)

    return CollectedPackage(
        pkg_dir=pkg_root.name,
        package_name=name,
        version=version,
        readme=readme,
        sub_readmes=sub_readmes,
        export_lines=export_lines,
        stories=stories,
        fingerprint=fingerprint,
    )


def iter_package_dirs(packages_root: Path) -> list[Path]:
    """Return immediate subdirectories of packages_root that look like packages."""
    result: list[Path] = []
    try:
        for entry in sorted(packages_root.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in _ALWAYS_SKIP:
                continue
            # Must have package.json or src/ to be considered a package
            if (entry / "package.json").exists() or (entry / "src").is_dir():
                result.append(entry)
    except OSError:
        pass
    return result
