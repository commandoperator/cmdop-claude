"""Sidecar init — generate initial .claude/ files for bare projects."""
from pathlib import Path

from sdkrouter import Model

from ...models.sidecar import InitResult, LLMInitResponse
from ...sidecar.prompts import INIT_SYSTEM, INIT_USER
from ...sidecar.tree_summarizer import TreeSummarizer
from ._base import SidecarBase

# Files that signal a project root or subproject
_PROJECT_MARKERS = {
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
    "Gemfile", "pom.xml", "build.gradle", "composer.json",
}

# Entry point filenames
_ENTRY_NAMES = {
    "main.py", "app.py", "index.ts", "index.js", "server.py", "server.ts",
    "main.go", "main.rs", "__main__.py", "manage.py", "cli.py",
    "index.tsx", "index.jsx", "main.ts", "cmd.go",
}

# Makefile target names
_MAKEFILE_NAMES = {"Makefile", "makefile", "GNUmakefile"}

_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb",
    ".toml", ".yaml", ".yml", ".json", ".sh", ".mjs", ".cjs",
})


def _classify_top_dirs(root: Path) -> str:
    """Classify top-level dirs as [own] or [external] based on nested project markers.

    A directory is [external] if it contains its own pyproject.toml/package.json/etc.
    at depth 1-2 — meaning it's a separate project (submodule, vendored lib, archive).
    Everything else is [own].
    """
    lines: list[str] = []
    try:
        entries = sorted(root.iterdir())
    except (PermissionError, OSError):
        return ""

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        # Check if this dir contains its own project config (= external)
        is_external = False
        try:
            for child in entry.iterdir():
                if child.is_file() and child.name in _PROJECT_MARKERS:
                    is_external = True
                    break
            if not is_external:
                # Check one level deeper
                for child in entry.iterdir():
                    if child.is_dir():
                        for grandchild in child.iterdir():
                            if grandchild.is_file() and grandchild.name in _PROJECT_MARKERS:
                                is_external = True
                                break
                    if is_external:
                        break
        except (PermissionError, OSError):
            pass
        tag = "[external]" if is_external else "[own]"
        lines.append(f"{entry.name}/ {tag}")

    return "\n".join(lines)


def _read_readme(root: Path, max_chars: int = 600) -> str:
    """Read first N chars of README.md if it exists."""
    for name in ("README.md", "readme.md", "README.rst", "README"):
        p = root / name
        if p.exists() and p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")[:max_chars]
            except Exception:
                pass
    return ""


def _find_all_project_configs(root: Path, max_depth: int = 5) -> list[dict]:
    """Find all pyproject.toml/package.json/etc. in the tree — reveals monorepo structure."""
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
                    text = entry.read_text(encoding="utf-8", errors="replace")
                    info["excerpt"] = text[:300]
                except Exception:
                    pass
                configs.append(info)
            elif entry.is_dir() and not should_exclude_dir(name, entry_rel, gitignore):
                _walk(entry, depth + 1, entry_rel)

    _walk(root, 0, "")
    return configs


def _find_makefiles(root: Path, max_depth: int = 4) -> str:
    """Find Makefiles anywhere in the tree — extract targets with path context."""
    from ...sidecar.exclusions import should_exclude_dir, load_gitignore

    gitignore = load_gitignore(root)
    all_targets: list[str] = []

    def _walk(current: Path, depth: int, rel: str) -> None:
        if depth > max_depth:
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


def _find_entry_points(root: Path, max_depth: int = 5) -> str:
    """Find entry points deep in the tree — not just top 2 levels."""
    from ...sidecar.exclusions import should_exclude_dir, load_gitignore

    gitignore = load_gitignore(root)
    entries: list[str] = []

    def _walk(current: Path, depth: int, rel: str) -> None:
        if depth > max_depth or len(entries) >= 20:
            return
        try:
            items = sorted(current.iterdir())
        except (PermissionError, OSError):
            return

        for item in items:
            name = item.name
            item_rel = f"{rel}/{name}" if rel else name
            if item.is_file() and name in _ENTRY_NAMES:
                # Read first line for context
                hint = ""
                try:
                    first_line = item.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
                    if first_line.startswith(("#!", "import ", "from ", "package ", "module ")):
                        hint = f" ({first_line[:60]})"
                except Exception:
                    pass
                entries.append(f"{item_rel}{hint}")
            elif item.is_dir() and not should_exclude_dir(name, item_rel, gitignore):
                _walk(item, depth + 1, item_rel)

    _walk(root, 0, "")
    return "\n".join(entries) if entries else "none detected"


def _build_smart_snippets(root: Path, max_snippets: int = 20, allowed_top_dirs: set[str] | None = None) -> str:
    """Build code snippets prioritized by importance, not alphabetical order.

    Priority order:
    1. Project configs (pyproject.toml, package.json) — reveal tech stack
    2. Entry points (main.py, manage.py, cli.py) — reveal what the project does
    3. High-value files (Dockerfile, docker-compose, etc.) — reveal infrastructure
    4. Regular code files — fill remaining slots
    """
    from ...sidecar.exclusions import (
        is_sensitive_content, is_sensitive_file, scan_project_dirs,
    )

    snippets: list[str] = []
    seen_paths: set[str] = set()

    def _add_snippet(fpath: Path, rel_path: str, lines: int = 5) -> bool:
        if rel_path in seen_paths:
            return False
        if is_sensitive_file(fpath.name):
            return False
        if not fpath.exists() or not fpath.is_file():
            return False
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
            first_lines = "\n".join(text.splitlines()[:lines])
            if is_sensitive_content(first_lines):
                return False
            snippets.append(f"### {rel_path}\n```\n{first_lines}\n```")
            seen_paths.add(rel_path)
            return True
        except Exception:
            return False

    try:
        dirs = scan_project_dirs(root, max_depth=5, max_dirs=50)
    except Exception:
        return ""

    # Filter to allowed top-level dirs if provided (from tree summarizer)
    if allowed_top_dirs:
        dirs = [
            d for d in dirs
            if d.path == "." or d.path.split("/")[0] in allowed_top_dirs
        ]

    # Pass 1: project configs (pyproject.toml, package.json, etc.)
    for d in dirs:
        for fname in d.file_names:
            if fname in _PROJECT_MARKERS:
                rel = f"{d.path}/{fname}" if d.path != "." else fname
                fpath = root / d.path / fname if d.path != "." else root / fname
                _add_snippet(fpath, rel, lines=8)
                if len(snippets) >= max_snippets:
                    return "\n\n".join(snippets)

    # Pass 2: entry points
    for d in dirs:
        for fname in d.file_names:
            if fname in _ENTRY_NAMES:
                rel = f"{d.path}/{fname}" if d.path != "." else fname
                fpath = root / d.path / fname if d.path != "." else root / fname
                _add_snippet(fpath, rel, lines=5)
                if len(snippets) >= max_snippets:
                    return "\n\n".join(snippets)

    # Pass 3: remaining code files (skip already seen, prioritize diverse dirs)
    dirs_seen: set[str] = set()
    for d in dirs:
        if d.path in dirs_seen:
            continue
        for fname in d.file_names[:2]:
            if fname in seen_paths:
                continue
            if not any(fname.endswith(ext) for ext in _CODE_EXTENSIONS):
                continue
            rel = f"{d.path}/{fname}" if d.path != "." else fname
            fpath = root / d.path / fname if d.path != "." else root / fname
            if _add_snippet(fpath, rel, lines=3):
                dirs_seen.add(d.path)
                break
            if len(snippets) >= max_snippets:
                return "\n\n".join(snippets)

    return "\n\n".join(snippets) or ""



def _build_fallback_claude_md(
    deps: str, dirs: str, entry_points: str, makefiles: str, readme: str,
    configs: list[dict],
) -> str:
    """Generate CLAUDE.md from scan data without LLM — used when API fails."""
    lines = ["# Project Documentation\n"]

    # Tech stack from deps
    if deps and deps != "(none detected)":
        lines.append("## Tech Stack")
        for dep in deps.split(", ")[:15]:
            lines.append(f"- {dep}")
        lines.append("")

    # Commands from Makefiles
    if makefiles and makefiles != "(no Makefile)":
        lines.append("## Commands")
        for mk_line in makefiles.splitlines()[:10]:
            lines.append(f"- `{mk_line.strip()}`")
        lines.append("")

    # Architecture from dirs + entry points
    lines.append("## Architecture")
    if dirs and dirs != "(none)":
        lines.append(f"Top directories: {dirs}")
        lines.append("")
    if entry_points and entry_points != "none detected":
        lines.append("Entry points:")
        for ep in entry_points.splitlines()[:10]:
            lines.append(f"- {ep}")
        lines.append("")

    # Monorepo structure
    if len(configs) > 3:
        lines.append("## Monorepo Structure")
        for cfg in configs[:10]:
            lines.append(f"- `{cfg['path']}` ({cfg['type']})")
        lines.append("")

    # Workflow
    lines.append("## Workflow")
    lines.append("- Before complex tasks, check `.claude/plans/` for existing plans and save new plans there")
    lines.append("- Periodically check `.claude/.sidecar/tasks/` for pending review items")
    lines.append("- After major changes, run `sidecar_scan` to review docs and `sidecar_map` to update the project map")
    lines.append("- Read `.claude/rules/` for project-specific coding guidelines")
    lines.append("- When working with external APIs, databases, browsers, or new tools — check if a relevant MCP plugin exists via `make -C .claude dashboard` (Plugin Browser tab)")
    lines.append("- Keep this file under 200 lines — move detailed rules to `.claude/rules/*.md`")
    lines.append("")

    # Key rules
    lines.append("## Key Rules")
    lines.append("- Check local Makefile for available commands (`make help`)")
    lines.append("- Run tests before committing (`make test`)")
    lines.append("- This file was auto-generated from project scan — review and refine")
    lines.append("")

    return "\n".join(lines)


class InitMixin(SidecarBase):
    """Project initialization — generate CLAUDE.md + rules from scan."""

    def init_project(self) -> InitResult:
        """Generate initial .claude/ files for a project that has none."""
        project_root = self._claude_dir.parent

        # Check both common locations
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

        # Discover monorepo structure
        configs = _find_all_project_configs(project_root)
        pyproject_block = ""
        if configs:
            parts = []
            for cfg in configs:
                excerpt = cfg.get("excerpt", "")[:150]
                parts.append(f"**{cfg['path']}**:\n{excerpt}")
            pyproject_block = "\n\n".join(parts)

        # --- Phase 1: Git context — classify own vs external repos ---
        # GitContextService finds all .git repos recursively and classifies each
        # via LLM. Returns own_top_dirs: set[str] — only dirs with active human commits.
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
            pass  # graceful fallback — continue without git context

        # --- Phase 2: Smart context gathering (filtered to own dirs) ---
        snippets_block = _build_smart_snippets(project_root, allowed_top_dirs=own_dirs)
        entry_points = _find_entry_points(project_root)
        makefile_block = _find_makefiles(project_root)

        # dirs_block for fallback (no-LLM path)
        dirs_block = _classify_top_dirs(project_root) or ", ".join(scan_result.top_dirs) or "(none)"

        # --- Phase 3: Tree pre-summarizer — chunked parallel LLM calls ---
        # Triggered when snippets_block is large (big/monorepo projects).
        # When own_dirs is provided (from GitContextService), only own dirs are summarized.
        # Merkle cache skips LLM for unchanged directories.
        summarizer = TreeSummarizer(self._sdk)
        tree_summary_block = ""
        if summarizer.should_summarize(snippets_block):
            try:
                from ...sidecar.merkle_cache import MerkleCache
                _cache_path = self._claude_dir / ".sidecar" / "merkle_cache.json"
                _model_id = Model.cheap(json=True)
                _merkle_cache = MerkleCache(_cache_path, _model_id)

                summaries = summarizer.summarize(
                    project_root, own_dirs=own_dirs, cache=_merkle_cache
                )
                tree_summary_block = summarizer.to_prompt_block(summaries)
                # If GitContextService didn't run, derive own_dirs from TreeSummarizer
                if own_dirs is None:
                    own_dirs = {s.path for s in summaries if s.role.value == "own"}
                if own_dirs:
                    snippets_block = _build_smart_snippets(
                        project_root, allowed_top_dirs=own_dirs
                    )
            except Exception:
                pass  # fallback: use raw snippets as-is

        user_msg = INIT_USER.format(
            deps_block=deps_block,
            git_repos_block=git_ctx_block or "(no git repos found)",
            tree_summary_block=tree_summary_block or f"\n{dirs_block}",
            commits_block=commits_block,
            entry_points=entry_points,
            readme_block=readme_block or "(no README)",
            makefile_block=makefile_block or "(no Makefile)",
            pyproject_block=pyproject_block or "(no project configs found)",
            snippets_block=snippets_block or "(no code snippets available)",
        )

        messages = [
            {"role": "system", "content": INIT_SYSTEM},
            {"role": "user", "content": user_msg},
        ]

        # Retry up to 3 times — DeepSeek structured output sometimes returns
        # empty or minimal content fields
        parsed = None
        tokens_used = 0
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
            parsed = None  # retry

        self._ensure_dirs()
        self._track_usage(tokens_used)

        if not parsed:
            # Fallback: generate CLAUDE.md from scan data without LLM
            fallback = _build_fallback_claude_md(
                deps=deps_block, dirs=dirs_block,
                entry_points=entry_points, makefiles=makefile_block,
                readme=readme_block, configs=configs,
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
            content = f.content
            fpath = project_root / path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")
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
