"""Filesystem scanner — collects documentation metadata without LLM calls."""
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cmdop_claude.models.sidecar import DocFile, DocScanResult

_PKG_NAME_RE = re.compile(r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_lazy_paths(text: str) -> Optional[list[str]]:
    """Extract paths list from YAML frontmatter, if present. Returns None if no paths found."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm_text = m.group(1)
    # Simple YAML list parsing: look for "paths:" key followed by "- item" lines
    paths_match = re.search(r"^paths\s*:\s*\n((?:\s*-\s*.+\n?)*)", fm_text, re.MULTILINE)
    if not paths_match:
        return None
    items = re.findall(r"^\s*-\s*['\"]?(.+?)['\"]?\s*$", paths_match.group(1), re.MULTILINE)
    return items if items else None


def _extract_pkg_name(dep_str: str) -> Optional[str]:
    """Extract package name from a PEP 508 dependency string."""
    m = _PKG_NAME_RE.match(dep_str.strip())
    return m.group(1) if m else None


def _file_modified_dt(path: Path) -> datetime:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _file_summary(path: Path, max_lines: int = 3) -> Optional[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:max_lines]
        return "\n".join(lines).strip() or None
    except Exception:
        return None


_MAX_SCAN_FILES = 1000
_MAX_FILE_BYTES = 500_000  # skip pathologically large files only (generated/binary)


def _file_priority(rel_path: str) -> int:
    """Lower = higher priority. CLAUDE.md first, then rules/, then plans/, rest last."""
    p = rel_path.replace("\\", "/")
    if p == "CLAUDE.md":
        return 0
    if p.startswith(".claude/rules/"):
        return 1
    if p.startswith(".claude/plans/"):
        return 3
    return 2


def scan_doc_files(claude_dir: Path) -> list[DocFile]:
    """Scan all .md files inside .claude/ and root CLAUDE.md.

    Files are prioritised: CLAUDE.md → rules/ → other .claude/ → plans/
    sorted by mtime descending within each priority group.
    No file count limit — content budget is enforced in _build_contents_block.
    """
    candidates: list[tuple[int, Path]] = []
    project_root = claude_dir.parent

    root_md = project_root / "CLAUDE.md"
    if root_md.exists():
        candidates.append((0, root_md))

    if claude_dir.exists():
        for md_file in claude_dir.rglob("*.md"):
            if ".sidecar" in md_file.parts:
                continue
            rel = _relative_path(md_file, project_root)
            candidates.append((_file_priority(rel), md_file))

    candidates.sort(key=lambda t: (t[0], -t[1].stat().st_mtime))
    candidates = candidates[:_MAX_SCAN_FILES]

    results: list[DocFile] = []
    for _, md_file in candidates:
        try:
            if md_file.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = md_file.read_text(encoding="utf-8")
            rel = _relative_path(md_file, project_root)
            lazy_paths = _parse_lazy_paths(text) if rel.startswith(".claude/rules/") else None
            results.append(
                DocFile(
                    path=rel,
                    modified_at=_file_modified_dt(md_file),
                    line_count=len(text.splitlines()),
                    summary=_file_summary(md_file),
                    lazy_paths=lazy_paths,
                )
            )
        except Exception:
            continue

    return results


def _relative_path(file_path: Path, root: Path) -> str:
    """Return path relative to project root, or filename if outside."""
    try:
        return str(file_path.relative_to(root))
    except ValueError:
        return file_path.name


def scan_dependencies() -> list[str]:
    """Read dependency names from requirements.txt and/or package.json."""
    deps: list[str] = []

    req_txt = Path("requirements.txt")
    if req_txt.exists():
        for line in req_txt.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                name = _extract_pkg_name(line)
                if name:
                    deps.append(name)

    pkg_json = Path("package.json")
    if pkg_json.exists():
        import json

        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies"):
                if section in data:
                    deps.extend(data[section].keys())
        except Exception:
            pass

    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        try:
            try:
                import tomllib  # Python 3.11+
            except ModuleNotFoundError:
                import tomli as tomllib  # type: ignore[no-redef]

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)

            # [project].dependencies (PEP 621)
            for dep_str in data.get("project", {}).get("dependencies", []):
                name = _extract_pkg_name(dep_str)
                if name:
                    deps.append(name)

            # [tool.poetry].dependencies (Poetry)
            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            if isinstance(poetry_deps, dict):
                for name in poetry_deps:
                    if name.lower() != "python":
                        deps.append(name)
        except Exception:
            pass

    return deps


def scan_git_log(max_entries: int = 20) -> list[str]:
    """Get recent git log entries (message + date, no diffs)."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{max_entries}", "--format=%ad %s", "--date=short"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return [
                line.strip()
                for line in result.stdout.strip().splitlines()
                if line.strip()
            ]
    except Exception:
        pass
    return []


def _is_junk_dir(name: str) -> bool:
    """Check if a directory name is junk (build artifacts, caches, etc.)."""
    from cmdop_claude.sidecar.utils.exclusions import GLOBAL_EXCLUDE_DIRS

    if name in GLOBAL_EXCLUDE_DIRS:
        return True
    if name.startswith("."):
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def scan_top_dirs(src_dir: str = "src") -> list[str]:
    """List top-level directories in the source root."""
    dirs: list[str] = []
    src = Path(src_dir)
    if src.exists():
        dirs = [d.name for d in sorted(src.iterdir()) if d.is_dir() and not _is_junk_dir(d.name)]
    # Fallback: list current directory's top-level dirs (exclude junk)
    if not dirs:
        dirs = [
            d.name
            for d in sorted(Path(".").iterdir())
            if d.is_dir() and not _is_junk_dir(d.name)
        ]
    return dirs


def full_scan(claude_dir: Path) -> DocScanResult:
    """Run all scanners and produce a complete DocScanResult."""
    return DocScanResult(
        files=scan_doc_files(claude_dir),
        dependencies=scan_dependencies(),
        recent_commits=scan_git_log(),
        top_dirs=scan_top_dirs(),
    )
