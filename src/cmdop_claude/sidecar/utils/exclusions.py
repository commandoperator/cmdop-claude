"""Exclusion engine — language-agnostic junk filtering + .gitignore parsing."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

# ── Global exclusion sets ────────────────────────────────────────────

GLOBAL_EXCLUDE_DIRS: frozenset[str] = frozenset({
    # VCS
    ".git", ".svn", ".hg", ".fossil",
    # Python
    "__pycache__", ".venv", "venv", ".env", ".eggs",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".nox",
    # JS / TS
    "node_modules", ".next", ".nuxt", ".svelte-kit", ".parcel-cache",
    "bower_components", ".yarn",
    # Build output
    "dist", "build", "out", "target", ".build", "_build",
    # IDE
    ".idea", ".vscode", ".vs", ".fleet",
    # Misc caches
    "coverage", ".nyc_output", ".turbo", ".cache", ".gradle",
    # Our own output
    ".sidecar",
    # Internal docs (not part of project structure)
    "@dev", "@docs",
    # Ruby
    ".bundle",
    # Rust
    "target",
    # Go
    "vendor",
})

GLOBAL_EXCLUDE_PATTERNS: frozenset[str] = frozenset({
    "*.pyc", "*.pyo", "*.egg-info",
    "*.log", "*.lock",
    "*.min.js", "*.min.css", "*.map",
    "*.o", "*.so", "*.dylib", "*.dll", "*.a",
    "*.class", "*.jar",
    "*.wasm",
    ".DS_Store", "Thumbs.db",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "uv.lock",
    "Cargo.lock", "go.sum", "Gemfile.lock",
    "composer.lock",
})

SENSITIVE_FILES: frozenset[str] = frozenset({
    ".env", ".env.local", ".env.production", ".env.staging",
    ".env.development", ".env.test",
    "credentials.json", "service-account.json",
    "id_rsa", "id_ed25519", "id_ecdsa",
    ".netrc", ".npmrc", ".pypirc",
})

SENSITIVE_CONTENT_RE = re.compile(
    r"(api[_\-]?key|secret[_\-]?key|password|auth[_\-]?token)\s*[:=]|"
    r"-----BEGIN.*PRIVATE KEY-----|"
    r"aws_?(access|secret)|"
    r"sk-[a-zA-Z0-9]{20,}|"
    r"ghp_[a-zA-Z0-9]{36}|"
    r"gho_[a-zA-Z0-9]{36}|"
    r"database_url\s*=",
    re.IGNORECASE,
)


# ── Data types ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class DirInfo:
    """Lightweight directory metadata collected during scan."""

    path: str  # relative to project root
    file_names: tuple[str, ...]  # sorted filenames in this dir (no subdirs)
    file_count: int

    @property
    def depth(self) -> int:
        if self.path == ".":
            return 0
        return self.path.count("/") + 1


# ── .gitignore parser ────────────────────────────────────────────────


def load_gitignore(root: Path) -> list[str]:
    """Parse .gitignore into glob patterns. Returns empty list if not found."""
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return []

    patterns: list[str] = []
    try:
        for line in gitignore.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Negation patterns (!pattern) — skip, too complex for our needs
            if line.startswith("!"):
                continue
            # Remove trailing slash (dir indicator) — we match both
            line = line.rstrip("/")
            patterns.append(line)
    except Exception:
        pass
    return patterns


def _matches_gitignore(name: str, rel_path: str, patterns: list[str]) -> bool:
    """Check if a file/dir name or relative path matches any gitignore pattern."""
    for pat in patterns:
        if "/" in pat:
            # Path pattern — match against relative path
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(rel_path, f"**/{pat}"):
                return True
        else:
            # Name-only pattern — match against basename
            if fnmatch.fnmatch(name, pat):
                return True
    return False


# ── Core exclusion logic ─────────────────────────────────────────────


def should_exclude_dir(name: str, rel_path: str, gitignore_patterns: list[str]) -> bool:
    """Check if a directory should be excluded from scanning."""
    if name.startswith("."):
        return True
    if name in GLOBAL_EXCLUDE_DIRS:
        return True
    if any(fnmatch.fnmatch(name, p) for p in GLOBAL_EXCLUDE_PATTERNS):
        return True
    if _matches_gitignore(name, rel_path, gitignore_patterns):
        return True
    return False


def should_exclude_file(name: str, rel_path: str, gitignore_patterns: list[str]) -> bool:
    """Check if a file should be excluded from listing."""
    if any(fnmatch.fnmatch(name, p) for p in GLOBAL_EXCLUDE_PATTERNS):
        return True
    if name in SENSITIVE_FILES:
        return True
    if _matches_gitignore(name, rel_path, gitignore_patterns):
        return True
    return False


def is_sensitive_file(name: str) -> bool:
    """Check if a file is sensitive (should never have contents sent to LLM)."""
    if name in SENSITIVE_FILES:
        return True
    # Check common sensitive extensions
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".jks")):
        return True
    return False


def is_sensitive_content(text: str) -> bool:
    """Check if text contains sensitive patterns (API keys, secrets, etc.)."""
    return bool(SENSITIVE_CONTENT_RE.search(text))


# ── Project scanner ──────────────────────────────────────────────────


def scan_project_dirs(
    root: Path,
    max_depth: int = 3,
    max_dirs: int = 50,
) -> list[DirInfo]:
    """Walk project tree, exclude junk, return clean directory list.

    Returns directories sorted by depth (shallow first), then alphabetically.
    """
    gitignore_patterns = load_gitignore(root)
    result: list[DirInfo] = []

    def _walk(current: Path, depth: int, rel_prefix: str) -> None:
        if depth > max_depth or len(result) >= max_dirs:
            return

        # Collect files in current dir (non-excluded)
        try:
            entries = sorted(current.iterdir())
        except PermissionError:
            return

        file_names: list[str] = []
        subdirs: list[tuple[Path, str]] = []

        for entry in entries:
            name = entry.name
            rel = f"{rel_prefix}/{name}" if rel_prefix else name

            if entry.is_dir():
                if not should_exclude_dir(name, rel, gitignore_patterns):
                    subdirs.append((entry, rel))
            elif entry.is_file():
                if not should_exclude_file(name, rel, gitignore_patterns):
                    file_names.append(name)

        # Add current dir if it has files (skip empty dirs)
        dir_rel = rel_prefix or "."
        if file_names or (depth == 0):
            result.append(DirInfo(
                path=dir_rel,
                file_names=tuple(sorted(file_names)),
                file_count=len(file_names),
            ))

        # Recurse into subdirs
        for subdir_path, subdir_rel in subdirs:
            if len(result) >= max_dirs:
                break
            _walk(subdir_path, depth + 1, subdir_rel)

    _walk(root, 0, "")
    return result
