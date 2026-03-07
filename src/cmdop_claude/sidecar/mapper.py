"""Project map generator — scans directory structure and annotates with LLM."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sdkrouter import SDKRouter

from ..models.project_map import (
    DirAnnotation,
    LLMMapResponse,
    MapConfig,
    ProjectMap,
)
from .cache import AnnotationCache, dir_content_hash
from .exclusions import DirInfo, is_sensitive_content, is_sensitive_file, scan_project_dirs
from .prompts import MAP_SYSTEM, MAP_USER

# Entry point file patterns
_ENTRY_NAMES = frozenset({
    "main.py", "app.py", "server.py", "cli.py", "manage.py", "__main__.py",
    "index.ts", "index.js", "index.tsx", "index.jsx",
    "main.ts", "main.js", "app.ts", "app.js", "server.ts", "server.js",
    "main.go", "main.rs", "Main.java", "Program.cs",
    "middleware.ts", "middleware.js",
    "page.tsx", "page.jsx",  # Next.js
    "Makefile", "Dockerfile",
})


class ProjectMapper:
    """Generates and updates .claude/project-map.md."""

    __slots__ = ("_sdk", "_root", "_map_path", "_cache", "_model")

    def __init__(
        self,
        sdk: SDKRouter,
        project_root: Path,
        sidecar_dir: Path,
        model: str = "deepseek/deepseek-v3.2",
    ) -> None:
        self._sdk = sdk
        self._model = model
        self._root = project_root
        self._map_path = project_root / ".claude" / "project-map.md"
        self._cache = AnnotationCache(sidecar_dir / "map_cache.json")

    def generate(self, config: Optional[MapConfig] = None) -> ProjectMap:
        """Full generation: scan dirs -> check cache -> LLM annotate uncached -> write map."""
        if config is None:
            config = MapConfig()

        dirs = scan_project_dirs(self._root, config.max_depth, config.max_dirs)

        # Split into cached and uncached
        cached_annotations: dict[str, str] = {}
        uncached_dirs: list[DirInfo] = []

        for d in dirs:
            h = dir_content_hash(d)
            cached = self._cache.get(d.path, h)
            if cached is not None:
                cached_annotations[d.path] = cached
            else:
                uncached_dirs.append(d)

        # If everything is cached, skip LLM call
        if not uncached_dirs:
            return self._build_from_cache(dirs, cached_annotations)

        # Build LLM prompt for uncached dirs
        dirs_block = self._build_dirs_block(uncached_dirs)
        snippets_block = self._build_snippets_block(uncached_dirs)

        user_msg = MAP_USER.format(
            dirs_block=dirs_block,
            snippets_block=snippets_block,
        )

        response = self._sdk.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": MAP_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format=LLMMapResponse,
            temperature=0.2,
        )

        tokens_used = response.usage.total_tokens if response.usage else 0
        model_used = response.model or "unknown"

        parsed: Optional[LLMMapResponse] = response.choices[0].message.parsed

        # Merge LLM annotations with cache
        if parsed:
            for llm_dir in parsed.directories:
                # Normalize path: strip trailing slashes
                norm_path = llm_dir.path.rstrip("/")
                cached_annotations[norm_path] = llm_dir.annotation
                # Update cache
                matching = [d for d in dirs if d.path == norm_path]
                if matching:
                    h = dir_content_hash(matching[0])
                    self._cache.set(norm_path, h, llm_dir.annotation)

        # Cache uncached dirs that LLM didn't annotate (e.g., root ".")
        for d in uncached_dirs:
            if d.path not in cached_annotations:
                default_ann = self._default_annotation(d)
                cached_annotations[d.path] = default_ann
                h = dir_content_hash(d)
                self._cache.set(d.path, h, default_ann)

        # Prune stale cache entries
        valid_paths = {d.path for d in dirs}
        self._cache.prune(valid_paths)
        self._cache.save()

        # Build result
        dir_annotations = self._build_annotations(dirs, cached_annotations, parsed)
        entry_points = self._detect_entry_points(dirs, parsed)

        now = datetime.now(tz=timezone.utc)
        result = ProjectMap(
            generated_at=now,
            project_type=parsed.project_type if parsed else "unknown",
            root_annotation=parsed.root_summary if parsed else "Project",
            directories=dir_annotations,
            entry_points=entry_points,
            tokens_used=tokens_used,
            model_used=model_used,
        )

        self._write_map_md(result)
        return result

    def update_incremental(self, config: Optional[MapConfig] = None) -> ProjectMap:
        """Incremental update: only re-annotate changed directories."""
        # Same as generate — cache handles the incremental logic automatically
        return self.generate(config)

    def detect_changes(self) -> list[str]:
        """Use git diff to find changed directories since last commit."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(self._root),
            )
            if result.returncode != 0:
                return []
            changed_dirs: set[str] = set()
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line:
                    parent = str(Path(line).parent)
                    if parent != ".":
                        changed_dirs.add(parent)
            return sorted(changed_dirs)
        except Exception:
            return []

    def get_current_map(self) -> str:
        """Return current project-map.md content, or empty string."""
        if self._map_path.exists():
            return self._map_path.read_text(encoding="utf-8")
        return ""

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _default_annotation(d: DirInfo) -> str:
        """Generate a descriptive fallback annotation from directory contents."""
        if d.path == ".":
            return "Project root"
        key_files = [f for f in d.file_names[:5] if not f.startswith(".") and not f.startswith("__")]
        if key_files:
            return f"Contains {', '.join(key_files)}"
        return f"Directory with {d.file_count} files"

    def _build_dirs_block(self, dirs: list[DirInfo]) -> str:
        lines: list[str] = []
        for d in dirs:
            files_str = ", ".join(d.file_names[:15])
            if len(d.file_names) > 15:
                files_str += f" ... (+{len(d.file_names) - 15} more)"
            lines.append(f"- `{d.path}/` ({d.file_count} files): {files_str}")
        return "\n".join(lines) or "(no directories)"

    def _build_snippets_block(self, dirs: list[DirInfo]) -> str:
        """Read first 5 lines of key files for context."""
        snippets: list[str] = []
        for d in dirs:
            for fname in d.file_names[:5]:
                if is_sensitive_file(fname):
                    continue
                fpath = self._root / d.path / fname if d.path != "." else self._root / fname
                if not fpath.exists() or not fpath.is_file():
                    continue
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                    first_lines = "\n".join(text.splitlines()[:5])
                    if is_sensitive_content(first_lines):
                        continue
                    snippets.append(f"### {d.path}/{fname}\n```\n{first_lines}\n```")
                except Exception:
                    continue
                if len(snippets) >= 20:
                    return "\n\n".join(snippets)
        return "\n\n".join(snippets) or "(no snippets available)"

    def _build_from_cache(
        self, dirs: list[DirInfo], cached: dict[str, str]
    ) -> ProjectMap:
        """Build ProjectMap entirely from cache (no LLM call)."""
        dir_annotations = [
            DirAnnotation(
                path=d.path,
                annotation=cached.get(d.path, f"Directory with {d.file_count} files"),
                file_count=d.file_count,
                has_entry_point=any(f in _ENTRY_NAMES for f in d.file_names),
                entry_point_name=next(
                    (f for f in d.file_names if f in _ENTRY_NAMES), None
                ),
            )
            for d in dirs
        ]
        entry_points = [
            f"{a.path}/{a.entry_point_name}"
            for a in dir_annotations
            if a.has_entry_point and a.entry_point_name
        ]
        now = datetime.now(tz=timezone.utc)

        # Try to read project_type from existing map
        existing = self.get_current_map()
        project_type = "unknown"
        root_annotation = "Project"
        if existing:
            for line in existing.splitlines():
                if line.startswith("> ") and "—" in line:
                    parts = line[2:].split("—", 1)
                    project_type = parts[0].strip()
                    root_annotation = parts[1].strip() if len(parts) > 1 else "Project"
                    break

        result = ProjectMap(
            generated_at=now,
            project_type=project_type,
            root_annotation=root_annotation,
            directories=dir_annotations,
            entry_points=entry_points,
            tokens_used=0,
            model_used="cache",
        )
        self._write_map_md(result)
        return result

    def _build_annotations(
        self,
        dirs: list[DirInfo],
        annotations: dict[str, str],
        parsed: Optional[LLMMapResponse],
    ) -> list[DirAnnotation]:
        """Build DirAnnotation list from dirs + merged annotations."""
        # Build entry point info from parsed response
        entry_info: dict[str, tuple[bool, Optional[str]]] = {}
        if parsed:
            for llm_dir in parsed.directories:
                entry_info[llm_dir.path.rstrip("/")] = (llm_dir.is_entry_point, llm_dir.entry_file)

        result: list[DirAnnotation] = []
        for d in dirs:
            ann = annotations.get(d.path, f"Directory with {d.file_count} files")
            is_entry, entry_file = entry_info.get(d.path, (False, None))
            # Also check filenames directly
            if not is_entry:
                local_entry = next((f for f in d.file_names if f in _ENTRY_NAMES), None)
                if local_entry:
                    is_entry = True
                    entry_file = local_entry

            result.append(DirAnnotation(
                path=d.path,
                annotation=ann,
                file_count=d.file_count,
                has_entry_point=is_entry,
                entry_point_name=entry_file,
            ))
        return result

    def _detect_entry_points(
        self, dirs: list[DirInfo], parsed: Optional[LLMMapResponse]
    ) -> list[str]:
        """Collect entry point paths (deduplicated, normalized)."""
        seen: set[str] = set()
        entries: list[str] = []

        def _add(path: str) -> None:
            # Normalize: strip trailing slashes, collapse double slashes
            normalized = path.rstrip("/").replace("//", "/")
            if normalized not in seen:
                seen.add(normalized)
                entries.append(normalized)

        # From LLM response
        if parsed:
            for llm_dir in parsed.directories:
                if llm_dir.is_entry_point and llm_dir.entry_file:
                    _add(f"{llm_dir.path.rstrip('/')}/{llm_dir.entry_file}")

        # From filename detection
        for d in dirs:
            for fname in d.file_names:
                if fname in _ENTRY_NAMES:
                    path = f"{d.path}/{fname}" if d.path != "." else fname
                    _add(path)

        return entries

    def _write_map_md(self, project_map: ProjectMap) -> None:
        """Render project-map.md."""
        lines = [
            "# Project Map",
            f"> {project_map.project_type} — {project_map.root_annotation}",
            f"> Generated: {project_map.generated_at.isoformat()}",
            "",
            "## Structure",
            "",
        ]

        # Group by depth for indentation
        for d in project_map.directories:
            if d.path == ".":
                continue  # root files listed separately if needed
            indent = "  " * (d.path.count("/"))
            entry_marker = f" **[entry: {d.entry_point_name}]**" if d.has_entry_point else ""
            lines.append(f"{indent}- `{d.path}/` — {d.annotation}{entry_marker}")

        if project_map.entry_points:
            lines.extend(["", "## Entry Points", ""])
            for ep in project_map.entry_points:
                lines.append(f"- `{ep}`")

        lines.extend([
            "",
            "---",
            f"Model: {project_map.model_used} | Tokens: {project_map.tokens_used}",
        ])

        self._map_path.parent.mkdir(parents=True, exist_ok=True)
        self._map_path.write_text("\n".join(lines), encoding="utf-8")
