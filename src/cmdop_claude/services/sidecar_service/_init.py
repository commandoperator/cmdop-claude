"""Sidecar init — generate initial .claude/ files for bare projects.

Two-step pipeline:
  Step 1 (cheap LLM): given file tree → select which files to read
  Step 2 (balanced LLM): read selected files → generate CLAUDE.md + rules
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sdkrouter import Model, SDKRouter

from ...models.sidecar import InitResult, LLMInitResponse, LLMFileSelectResponse
from ...sidecar.prompts import (
    FILE_SELECT_SYSTEM, FILE_SELECT_USER,
    INIT_SYSTEM, INIT_USER,
)
from ...sidecar.tree_summarizer import TreeSummarizer
from ._base import SidecarBase

# Files that signal a project root or subproject (still needed for monorepo detection)
_PROJECT_MARKERS = {
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "Gemfile", "pom.xml", "build.gradle", "composer.json",
}

# Makefile names
_MAKEFILE_NAMES = {"Makefile", "makefile", "GNUmakefile"}

# Extensions worth reading
_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb",
    ".toml", ".yaml", ".yml", ".json", ".sh", ".mjs", ".cjs", ".cs",
    ".php", ".swift", ".kt", ".scala", ".ex", ".exs",
})

# Dirs/files always excluded from scanning
_SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    "dist", "build", ".tox", ".eggs", ".git", ".sidecar",
    "@sources", "@archive", "@vendor", "@dev", "@docs",
})


def _read_readme(root: Path, max_chars: int = 800) -> str:
    for name in ("README.md", "readme.md", "README.rst", "README"):
        p = root / name
        if p.exists() and p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
            except Exception:
                pass
    return ""


def _find_all_project_configs(root: Path, max_depth: int = 5) -> list[dict]:
    """Find all pyproject.toml/package.json/etc. — reveals monorepo structure."""
    from ...sidecar.exclusions import should_exclude_dir, load_gitignore

    gitignore = load_gitignore(root)
    configs: list[dict] = []

    def _walk(current: Path, depth: int, rel: str) -> None:
        if depth > max_depth or len(configs) >= 10:
            return
        try:
            entries = sorted(current.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            name = entry.name
            entry_rel = f"{rel}/{name}" if rel else name
            if entry.is_file() and name in _PROJECT_MARKERS:
                info: dict = {"path": entry_rel, "type": name}
                try:
                    info["excerpt"] = entry.read_text(encoding="utf-8", errors="replace")[:300]
                except Exception:
                    pass
                configs.append(info)
            elif entry.is_dir() and not should_exclude_dir(name, entry_rel, gitignore):
                _walk(entry, depth + 1, entry_rel)

    _walk(root, 0, "")
    return configs


def _find_makefiles(
    root: Path, max_depth: int = 4, allowed_top_dirs: set[str] | None = None
) -> str:
    from ...sidecar.exclusions import should_exclude_dir, load_gitignore

    gitignore = load_gitignore(root)
    all_targets: list[str] = []

    def _walk(current: Path, depth: int, rel: str) -> None:
        if depth > max_depth:
            return
        if depth == 1 and allowed_top_dirs is not None:
            if rel.split("/")[0] not in allowed_top_dirs:
                return
        try:
            entries = sorted(current.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            name = entry.name
            entry_rel = f"{rel}/{name}" if rel else name
            if entry.is_file() and name in _MAKEFILE_NAMES:
                targets: list[str] = []
                try:
                    for line in entry.read_text(encoding="utf-8").splitlines():
                        if line and not line.startswith(("\t", " ", "#", ".")) and ":" in line:
                            target = line.split(":")[0].strip()
                            if target and not target.startswith("$"):
                                targets.append(target)
                except Exception:
                    pass
                if targets:
                    prefix = f"{rel}/" if rel else ""
                    all_targets.append(f"{prefix}Makefile: {', '.join(targets[:15])}")
            elif entry.is_dir() and not should_exclude_dir(name, entry_rel, gitignore):
                _walk(entry, depth + 1, entry_rel)

    _walk(root, 0, "")
    return "\n".join(all_targets[:10]) if all_targets else ""


def _build_file_tree(root: Path, allowed_top_dirs: set[str] | None = None, max_depth: int = 5) -> str:
    """Build a compact indented file tree for LLM file selection.

    Returns lines like:
        src/
          cmdop_claude/
            _config.py
            models/
              sidecar.py
    """
    from ...sidecar.exclusions import should_exclude_dir, load_gitignore

    gitignore = load_gitignore(root)
    lines: list[str] = []

    def _walk(current: Path, depth: int, rel: str) -> None:
        if depth > max_depth:
            return
        if depth == 1 and allowed_top_dirs is not None:
            if rel.split("/")[0] not in allowed_top_dirs:
                return
        try:
            entries = sorted(current.iterdir(), key=lambda e: (e.is_file(), e.name))
        except (PermissionError, OSError):
            return

        indent = "  " * depth
        for entry in entries:
            name = entry.name
            if name.startswith(".") and name not in {".env.example", ".github"}:
                continue
            entry_rel = f"{rel}/{name}" if rel else name
            if entry.is_dir():
                if name in _SKIP_DIRS:
                    continue
                if should_exclude_dir(name, entry_rel, gitignore):
                    continue
                lines.append(f"{indent}{name}/")
                _walk(entry, depth + 1, entry_rel)
            else:
                if any(name.endswith(ext) for ext in _CODE_EXTENSIONS) or name in _PROJECT_MARKERS:
                    lines.append(f"{indent}{name}")

    _walk(root, 0, "")
    return "\n".join(lines[:500])  # cap at 500 lines to stay cheap


def _select_files_to_read(
    sdk: "SDKRouter", file_tree: str, readme: str, deps: str
) -> list[str]:
    """Step 1: Ask cheap LLM to pick which files are most informative.

    Returns list of relative paths (strings).
    """
    user_msg = FILE_SELECT_USER.format(
        file_tree=file_tree,
        readme_block=readme or "(no README)",
        deps_block=deps or "(none)",
    )

    try:
        response = sdk.parse(
            model=Model.cheap(json=True),
            messages=[
                {"role": "system", "content": FILE_SELECT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format=LLMFileSelectResponse,
            temperature=0.0,
            max_tokens=1024,
        )
        parsed = response.choices[0].message.parsed
        if parsed and parsed.files:
            return [str(f) for f in parsed.files[:25]]
    except Exception:
        pass

    return []


def _read_selected_files(
    root: Path, selected: list[str], lines_per_file: int = 40
) -> str:
    """Read selected files, returning a formatted snippets block."""
    from ...sidecar.exclusions import is_sensitive_content, is_sensitive_file

    snippets: list[str] = []
    for rel_path in selected:
        fpath = root / rel_path
        if not fpath.exists() or not fpath.is_file():
            continue
        if is_sensitive_file(fpath.name):
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
            content = "\n".join(text.splitlines()[:lines_per_file])
            if is_sensitive_content(content):
                continue
            snippets.append(f"### {rel_path}\n```\n{content}\n```")
        except Exception:
            continue

    return "\n\n".join(snippets)


def _classify_top_dirs(root: Path) -> str:
    lines: list[str] = []
    try:
        entries = sorted(root.iterdir())
    except (PermissionError, OSError):
        return ""

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        is_external = False
        try:
            for child in entry.iterdir():
                if child.is_file() and child.name in _PROJECT_MARKERS:
                    is_external = True
                    break
        except (PermissionError, OSError):
            pass
        tag = "[external]" if is_external else "[own]"
        lines.append(f"{entry.name}/ {tag}")

    return "\n".join(lines)


def _build_fallback_claude_md(
    deps: str, dirs: str, makefiles: str, readme: str, configs: list[dict],
) -> str:
    lines = ["# Project Documentation\n"]

    if deps and deps != "(none detected)":
        lines.append("## Tech Stack")
        for dep in deps.split(", ")[:15]:
            lines.append(f"- {dep}")
        lines.append("")

    if makefiles and makefiles != "(no Makefile)":
        lines.append("## Commands")
        for mk_line in makefiles.splitlines()[:10]:
            lines.append(f"- `{mk_line.strip()}`")
        lines.append("")

    if readme:
        lines.append("## Overview")
        lines.append(readme[:300].strip())
        lines.append("")

    lines.append("## Architecture")
    if dirs and dirs != "(none)":
        lines.append(f"Top directories:\n{dirs}")
        lines.append("")

    if len(configs) > 3:
        lines.append("## Monorepo Structure")
        for cfg in configs[:10]:
            lines.append(f"- `{cfg['path']}` ({cfg['type']})")
        lines.append("")

    lines.append("## Workflow")
    lines.append("- Before complex tasks, check `.claude/plans/` for existing plans")
    lines.append("- Periodically check `.claude/.sidecar/tasks/` for pending review items")
    lines.append("- After major changes, run `sidecar_scan` and `sidecar_map`")
    lines.append("- Read `.claude/rules/` for project-specific coding guidelines")
    lines.append("- Keep this file under 200 lines — move detailed rules to `.claude/rules/*.md`")
    lines.append("")

    lines.append("## Key Rules")
    lines.append("- This file was auto-generated from project scan — review and refine")
    lines.append("")

    return "\n".join(lines)


class InitMixin(SidecarBase):
    """Project initialization — generate CLAUDE.md + rules from scan."""

    def init_project(self) -> InitResult:
        """Generate initial .claude/ files for a project that has none."""
        project_root = self._claude_dir.parent

        for candidate in ("CLAUDE.md", ".claude/CLAUDE.md"):
            p = project_root / candidate
            if p.exists() and p.stat().st_size > 50:
                return InitResult(
                    files_created=[],
                    tokens_used=0,
                    model_used=f"skipped — {candidate} already exists",
                )

        scan_result = self.scan()
        deps_block = ", ".join(scan_result.dependencies) or "(none detected)"
        commits_block = "\n".join(scan_result.recent_commits[:10]) or "(no git history)"
        readme_block = _read_readme(project_root)

        configs = _find_all_project_configs(project_root)
        pyproject_block = ""
        if configs:
            parts = []
            for cfg in configs:
                excerpt = cfg.get("excerpt", "")[:150]
                parts.append(f"**{cfg['path']}**:\n{excerpt}")
            pyproject_block = "\n\n".join(parts)

        # --- Phase 1: Git context — classify own vs external repos ---
        own_dirs: set[str] | None = None
        git_ctx_block = ""
        try:
            from ...sidecar.git_context import GitContextService
            git_ctx = GitContextService(self._sdk).collect(
                project_root, claude_dir=self._claude_dir
            )
            if git_ctx.own_top_dirs:
                own_dirs = git_ctx.own_top_dirs
            git_ctx_block = git_ctx.to_prompt_block()
        except Exception:
            pass

        # --- Phase 2: Tree pre-summarizer (large/monorepo projects) ---
        summarizer = TreeSummarizer(self._sdk)
        tree_summary_block = ""
        file_tree = _build_file_tree(project_root, allowed_top_dirs=own_dirs)
        if summarizer.should_summarize(file_tree):
            try:
                from ...sidecar.merkle_cache import MerkleCache
                _cache_path = self._claude_dir / ".sidecar" / "merkle_cache.json"
                _merkle_cache = MerkleCache(_cache_path, Model.cheap(json=True))
                summaries = summarizer.summarize(
                    project_root, own_dirs=own_dirs, cache=_merkle_cache
                )
                tree_summary_block = summarizer.to_prompt_block(summaries)
                if own_dirs is None:
                    own_dirs = {s.path for s in summaries if s.role.value == "own"}
                # Rebuild file_tree filtered to own dirs
                if own_dirs:
                    file_tree = _build_file_tree(project_root, allowed_top_dirs=own_dirs)
            except Exception:
                pass

        makefile_block = _find_makefiles(project_root, allowed_top_dirs=own_dirs)
        dirs_block = _classify_top_dirs(project_root) or ", ".join(scan_result.top_dirs) or "(none)"

        # --- Phase 3: Step 1 — LLM selects which files to read ---
        tokens_used = 0
        selected_files = _select_files_to_read(
            self._sdk, file_tree, readme_block, deps_block
        )

        # --- Phase 3: Step 2 — Read selected files ---
        snippets_block = _read_selected_files(project_root, selected_files)

        # Fallback: if selection returned nothing, read project configs at minimum
        if not snippets_block:
            fallback_files = [
                cfg["path"] for cfg in configs
                if cfg.get("path")
            ]
            snippets_block = _read_selected_files(project_root, fallback_files, lines_per_file=20)

        user_msg = INIT_USER.format(
            deps_block=deps_block,
            git_repos_block=git_ctx_block or "(no git repos found)",
            tree_summary_block=tree_summary_block or f"\n{dirs_block}",
            commits_block=commits_block,
            readme_block=readme_block or "(no README)",
            makefile_block=makefile_block or "(no Makefile)",
            pyproject_block=pyproject_block or "(no project configs found)",
            snippets_block=snippets_block or "(no code snippets available)",
        )
        # Note: entry_points removed — LLM now selects entry point files directly in Step 1

        messages = [
            {"role": "system", "content": INIT_SYSTEM},
            {"role": "user", "content": user_msg},
        ]

        parsed = None
        model_used = "unknown"
        for _ in range(3):
            try:
                response = self._sdk.parse(
                    model=Model.balanced(json=True),
                    messages=messages,
                    response_format=LLMInitResponse,
                    temperature=0.3,
                    max_tokens=8192,
                )
            except Exception:
                continue
            tokens_used += response.usage.total_tokens if response.usage else 0
            model_used = response.model or "unknown"
            parsed = response.choices[0].message.parsed
            if parsed and any(
                len(f.content) > 100 and "\n" in f.content
                for f in parsed.files
            ):
                break
            parsed = None

        self._ensure_dirs()
        self._track_usage(tokens_used)

        if not parsed:
            fallback = _build_fallback_claude_md(
                deps=deps_block, dirs=dirs_block,
                makefiles=makefile_block, readme=readme_block, configs=configs,
            )
            fpath = project_root / "CLAUDE.md"
            fpath.write_text(fallback, encoding="utf-8")
            self._log_activity(
                "init", tokens=tokens_used, model="fallback",
                files_created=["CLAUDE.md"],
            )
            return InitResult(
                files_created=["CLAUDE.md"],
                tokens_used=tokens_used,
                model_used=f"fallback (LLM failed after {tokens_used} tokens)",
            )

        files_created: list[str] = []
        for f in parsed.files:
            path = f.path
            if path in (".claude/CLAUDE.md", ".claude\\CLAUDE.md"):
                path = "CLAUDE.md"
            fpath = project_root / path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(f.content, encoding="utf-8")
            files_created.append(path)

        self._log_activity(
            "init", tokens=tokens_used, model=model_used,
            files_created=files_created,
        )

        return InitResult(
            files_created=files_created,
            tokens_used=tokens_used,
            model_used=model_used,
        )
