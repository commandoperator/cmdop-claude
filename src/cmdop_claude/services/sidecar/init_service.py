"""InitService — generate initial .claude/ files for bare projects."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sdkrouter import Model

from cmdop_claude.models.sidecar.init import InitResult, LLMFileSelectResponse, LLMInitResponse
from cmdop_claude.sidecar.scan._sidecar_section import inject_sidecar_workflow
from cmdop_claude.sidecar.scan._rules_templates import (
    build_frontmatter,
    get_templates_for_deps,
)
from cmdop_claude.sidecar.utils.prompts import FILE_SELECT_SYSTEM, FILE_SELECT_USER, INIT_SYSTEM, INIT_USER
from cmdop_claude.sidecar.utils.text_utils import normalize_content
from cmdop_claude.sidecar.scan.tree_summarizer import TreeSummarizer

from .state import SidecarState

# Files that signal a project root or subproject
_PROJECT_MARKERS = {
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "Gemfile", "pom.xml", "build.gradle", "composer.json",
}
_MAKEFILE_NAMES = {"Makefile", "makefile", "GNUmakefile"}
_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb",
    ".toml", ".yaml", ".yml", ".json", ".sh", ".mjs", ".cjs", ".cs",
    ".php", ".swift", ".kt", ".scala", ".ex", ".exs",
})
_SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    "dist", "build", ".tox", ".eggs", ".git", ".sidecar",
    "@sources", "@archive", "@vendor", "@dev", "@docs",
})


class InitService:
    def __init__(self, state: SidecarState) -> None:
        self._s = state

    def init_project(self) -> InitResult:
        project_root = self._s.claude_dir.parent

        for candidate in ("CLAUDE.md", ".claude/CLAUDE.md"):
            p = project_root / candidate
            if p.exists() and p.stat().st_size > 50:
                return InitResult(
                    files_created=[],
                    tokens_used=0,
                    model_used=f"skipped — {candidate} already exists",
                )

        scan_result = self._s.scan()
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

        # Phase 1: Git context
        own_dirs: set[str] | None = None
        git_ctx_block = ""
        try:
            from cmdop_claude.sidecar.git.git_context import GitContextService
            git_ctx = GitContextService(self._s.sdk).collect(
                project_root, claude_dir=self._s.claude_dir
            )
            if git_ctx.own_top_dirs:
                own_dirs = git_ctx.own_top_dirs
            git_ctx_block = git_ctx.to_prompt_block()
        except Exception:
            pass

        # Phase 2: Tree pre-summarizer
        summarizer = TreeSummarizer(self._s.sdk)
        tree_summary_block = ""
        file_tree = _build_file_tree(project_root, allowed_top_dirs=own_dirs)
        if summarizer.should_summarize(file_tree):
            try:
                from cmdop_claude.sidecar.cache.merkle_cache import MerkleCache
                _cache_path = self._s.claude_dir / ".sidecar" / "merkle_cache.json"
                _merkle_cache = MerkleCache(_cache_path, Model.cheap(json=True))
                summaries = summarizer.summarize(
                    project_root, own_dirs=own_dirs, cache=_merkle_cache
                )
                tree_summary_block = summarizer.to_prompt_block(summaries)
                if own_dirs is None:
                    own_dirs = {s.path for s in summaries if s.role.value == "own"}
                if own_dirs:
                    file_tree = _build_file_tree(project_root, allowed_top_dirs=own_dirs)
            except Exception:
                pass

        makefile_block = _find_makefiles(project_root, allowed_top_dirs=own_dirs)
        dirs_block = _classify_top_dirs(project_root) or ", ".join(scan_result.top_dirs) or "(none)"

        # Phase 3: Step 1 — LLM selects files
        tokens_used = 0
        selected_files = self._select_files_to_read(file_tree, readme_block, deps_block)

        # Phase 3: Step 2 — Read selected files
        snippets_block = _read_selected_files(project_root, selected_files)
        if not snippets_block:
            fallback_files = [cfg["path"] for cfg in configs if cfg.get("path")]
            snippets_block = _read_selected_files(project_root, fallback_files, lines_per_file=20)

        docs_block, docs_workflow_hint, packages_hint = _build_docs_block()

        user_msg = INIT_USER.format(
            deps_block=deps_block,
            git_repos_block=git_ctx_block or "(no git repos found)",
            tree_summary_block=tree_summary_block or f"\n{dirs_block}",
            commits_block=commits_block,
            readme_block=readme_block or "(no README)",
            makefile_block=makefile_block or "(no Makefile)",
            pyproject_block=pyproject_block or "(no project configs found)",
            snippets_block=snippets_block or "(no code snippets available)",
            docs_block=docs_block,
            docs_workflow_hint=docs_workflow_hint,
        )

        messages = [
            {"role": "system", "content": INIT_SYSTEM},
            {"role": "user", "content": user_msg},
        ]

        parsed = None
        model_used = "unknown"
        for _ in range(3):
            try:
                result = self._s.llm.call(
                    model=Model.balanced(json=True),
                    messages=messages,
                    response_format=LLMInitResponse,
                    temperature=0.3,
                    max_tokens=8192,
                )
                tokens_used += result.tokens
                model_used = self._s.model
                if any(len(f.content) > 100 and "\n" in f.content for f in result.parsed.files):
                    parsed = result.parsed
                    break
            except Exception:
                continue

        self._s.ensure_dirs()
        self._s.track_usage(tokens_used)

        if not parsed:
            fallback = _build_fallback_claude_md(
                deps=deps_block, dirs=dirs_block,
                makefiles=makefile_block, readme=readme_block, configs=configs,
            )
            fallback = inject_sidecar_workflow(fallback, docs_workflow_hint, packages_hint)
            fpath = project_root / "CLAUDE.md"
            fpath.write_text(fallback, encoding="utf-8")
            self._s.log_activity(
                "init", tokens=tokens_used, model="fallback",
                files_created=["CLAUDE.md"],
            )
            return InitResult(
                files_created=["CLAUDE.md"],
                tokens_used=tokens_used,
                model_used=f"fallback (LLM failed after {tokens_used} tokens)",
            )

        # Build frontmatter lookup from templates based on detected deps
        dep_templates = get_templates_for_deps(scan_result.dependencies)
        _frontmatter_by_filename = {
            t.filename: build_frontmatter(t.paths_glob)
            for t in dep_templates
            if t.paths_glob is not None
        }

        files_created: list[str] = []
        for f in parsed.files:
            path = f.path
            if path in (".claude/CLAUDE.md", ".claude\\CLAUDE.md"):
                path = "CLAUDE.md"
            fpath = project_root / path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            raw = normalize_content(f.content)
            if fpath.name == "CLAUDE.md":
                raw = inject_sidecar_workflow(raw, docs_workflow_hint, packages_hint)
            elif path.startswith(".claude/rules/"):
                raw = _inject_rules_frontmatter(raw, fpath.name, _frontmatter_by_filename)
            fpath.write_text(raw + "\n", encoding="utf-8")
            files_created.append(path)

        self._s.log_activity(
            "init", tokens=tokens_used, model=model_used,
            files_created=files_created,
        )
        return InitResult(
            files_created=files_created,
            tokens_used=tokens_used,
            model_used=model_used,
        )

    def _select_files_to_read(self, file_tree: str, readme: str, deps: str) -> list[str]:
        user_msg = FILE_SELECT_USER.format(
            file_tree=file_tree,
            readme_block=readme or "(no README)",
            deps_block=deps or "(none)",
        )
        try:
            result = self._s.llm.call(
                model=Model.cheap(json=True),
                messages=[
                    {"role": "system", "content": FILE_SELECT_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=LLMFileSelectResponse,
                temperature=0.0,
                max_tokens=1024,
            )
            if result.parsed.files:
                return [str(f) for f in result.parsed.files[:25]]
        except Exception:
            pass
        return []


# ── Module-level helpers (pure functions) ─────────────────────────────────────

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
    from cmdop_claude.sidecar.utils.exclusions import should_exclude_dir, load_gitignore
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
    from cmdop_claude.sidecar.utils.exclusions import should_exclude_dir, load_gitignore
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


def _build_file_tree(
    root: Path, allowed_top_dirs: set[str] | None = None, max_depth: int = 5
) -> str:
    from cmdop_claude.sidecar.utils.exclusions import should_exclude_dir, load_gitignore
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
    return "\n".join(lines[:500])


def _read_selected_files(
    root: Path, selected: list[str], lines_per_file: int = 40
) -> str:
    from cmdop_claude.sidecar.utils.exclusions import is_sensitive_content, is_sensitive_file
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
    lines.append("## Key Rules")
    lines.append("- This file was auto-generated from project scan — review and refine")
    lines.append("")
    return "\n".join(lines)


def _inject_rules_frontmatter(
    content: str,
    filename: str,
    frontmatter_by_filename: dict[str, str],
) -> str:
    """Prepend paths frontmatter to a rules file if not already present and template exists."""
    if content.startswith("---"):
        return content  # Already has frontmatter
    fm = frontmatter_by_filename.get(filename)
    if fm:
        return fm + content
    return content


def _build_docs_block() -> tuple[str, str, str]:
    try:
        from cmdop_claude.models.config.cmdop_config import CmdopConfig
        cfg = CmdopConfig.load()
        sources = cfg.docs_sources
    except Exception:
        return "(no documentation sources configured)", "", ""

    lines = []
    for s in sources:
        desc = s.description or s.path
        lines.append(f"- **{desc}** — `docs_search` / `docs_get` MCP tools")

    docs_block = "\n".join(lines) if lines else "(no documentation sources configured)"

    docs_workflow_hint = ""
    if sources:
        source_names = ", ".join(s.description or s.path for s in sources if s.description or s.path)
        docs_workflow_hint = (
            f"Use `docs_search` to find relevant guides in: {source_names}. "
            "Call `docs_get` with the returned path to read the full file."
        )

    return docs_block, docs_workflow_hint, ""
