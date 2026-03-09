"""Tree pre-summarizer — classifies project dirs before init LLM call.

Splits top-level directories into chunks, runs DeepSeek structured output
on each chunk in parallel (asyncio), merges results. Only "own" dirs are
passed to the init LLM — external/vendor dirs are filtered out.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from cmdop_claude.models.sidecar import DirRole, LLMDirSummary, LLMTreeChunkResponse
from cmdop_claude.sidecar.cache.merkle_cache import MerkleCache, hash_dir
from cmdop_claude.sidecar.utils.prompts import TREE_CHUNK_SYSTEM, TREE_CHUNK_USER
from cmdop_claude.sidecar.scan.toon import to_toon

if TYPE_CHECKING:
    from sdkrouter import SDKRouter

# Trigger summarizer if snippets_block exceeds this length
SUMMARIZE_THRESHOLD = 5_000

# Dirs per LLM chunk
CHUNK_SIZE = 5

# Max files to list per directory in the prompt
MAX_FILES_PER_DIR = 20


def _list_dir(path: Path) -> list[str]:
    """Return sorted file/dir names in path (non-recursive, limited)."""
    try:
        names = sorted(p.name for p in path.iterdir())
        return names[:MAX_FILES_PER_DIR]
    except (PermissionError, OSError):
        return []


def _build_chunk_block(dirs: list[Path], root: Path) -> str:
    """Build the dirs_block for a chunk of directories."""
    tree: dict = {}
    for d in dirs:
        rel = str(d.relative_to(root))
        parts = rel.replace("\\", "/").split("/")
        node = tree
        for part in parts:
            node = node.setdefault(part, {})
        for name in _list_dir(d):
            child = d / name
            if child.is_dir():
                node.setdefault(name, {})
            else:
                node.setdefault(name, None)
    return to_toon(tree)


def _call_llm_chunk(sdk: "SDKRouter", dirs: list[Path], root: Path) -> LLMTreeChunkResponse | None:
    """Synchronous LLM call for one chunk. Returns None on failure."""
    from sdkrouter import Model

    dirs_block = _build_chunk_block(dirs, root)
    user_msg = TREE_CHUNK_USER.format(dirs_block=dirs_block)

    for _ in range(3):
        try:
            response = sdk.parse(
                model=Model.cheap(json=True),
                messages=[
                    {"role": "system", "content": TREE_CHUNK_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=LLMTreeChunkResponse,
                temperature=0.1,
                max_tokens=2048,
            )
            parsed = response.choices[0].message.parsed
            if parsed and parsed.dirs:
                return parsed
        except Exception:
            continue
    return None


async def _call_llm_chunk_async(
    sdk: "SDKRouter", dirs: list[Path], root: Path
) -> LLMTreeChunkResponse | None:
    """Run synchronous LLM call in thread pool to enable parallelism."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call_llm_chunk, sdk, dirs, root)


class TreeSummarizer:
    """Pre-summarizes large project trees before passing to init LLM."""

    def __init__(self, sdk: "SDKRouter") -> None:
        self._sdk = sdk

    def should_summarize(self, snippets_block: str) -> bool:
        return len(snippets_block) > SUMMARIZE_THRESHOLD

    def summarize(
        self,
        root: Path,
        own_dirs: set[str] | None = None,
        cache: MerkleCache | None = None,
    ) -> list[LLMDirSummary]:
        """Classify top-level dirs. Cache hits skip LLM entirely."""
        top_dirs = self._get_top_dirs(root, own_dirs)
        if not top_dirs:
            return []

        # Split into cached (no LLM) and uncached (need LLM)
        cached_results: list[LLMDirSummary] = []
        dirs_needing_llm: list[Path] = []

        if cache is not None:
            for d in top_dirs:
                rel = str(d.relative_to(root))
                dir_hash = hash_dir(d)
                entry = cache.get(rel, dir_hash)
                if entry:
                    cached_results.append(LLMDirSummary(
                        path=rel,
                        role=DirRole(entry["role"]),
                        tech_stack=entry.get("tech_stack", []),
                        key_files=entry.get("key_files", []),
                        commands=entry.get("commands", []),
                    ))
                else:
                    dirs_needing_llm.append(d)
        else:
            dirs_needing_llm = top_dirs

        # Only call LLM for dirs that aren't cached
        llm_results: list[LLMDirSummary] = []
        if dirs_needing_llm:
            chunks = [
                dirs_needing_llm[i: i + CHUNK_SIZE]
                for i in range(0, len(dirs_needing_llm), CHUNK_SIZE)
            ]
            chunk_responses: list[LLMTreeChunkResponse | None] = asyncio.run(
                self._run_chunks(chunks, root)
            )
            for chunk_result in chunk_responses:
                if chunk_result:
                    for summary in chunk_result.dirs:
                        llm_results.append(summary)
                        # Persist to cache
                        if cache is not None:
                            d_path = root / summary.path
                            if d_path.is_dir():
                                cache.put(
                                    summary.path,
                                    hash_dir(d_path),
                                    summary.role.value,
                                    summary.tech_stack,
                                    summary.key_files,
                                    summary.commands,
                                )
            if cache is not None:
                cache.flush()

        return cached_results + llm_results

    async def _run_chunks(
        self, chunks: list[list[Path]], root: Path
    ) -> list[LLMTreeChunkResponse | None]:
        tasks = [
            _call_llm_chunk_async(self._sdk, chunk, root)
            for chunk in chunks
        ]
        return await asyncio.gather(*tasks)

    def _get_top_dirs(self, root: Path, own_dirs: set[str] | None = None) -> list[Path]:
        """Return top-level directories, skipping hidden and known junk.

        If own_dirs is provided (from GitContextService), only those dirs are returned.
        """
        from cmdop_claude.sidecar.utils.exclusions import GLOBAL_EXCLUDE_DIRS

        dirs: list[Path] = []
        try:
            for entry in sorted(root.iterdir()):
                if not entry.is_dir():
                    continue
                if entry.name.startswith("."):
                    continue
                if entry.name in GLOBAL_EXCLUDE_DIRS:
                    continue
                # If GitContextService gave us own_dirs, filter to those only
                if own_dirs is not None and entry.name not in own_dirs:
                    continue
                dirs.append(entry)
        except (PermissionError, OSError):
            pass
        return dirs

    def to_prompt_block(self, summaries: list[LLMDirSummary]) -> str:
        """Format summaries into a compact block for the init prompt."""
        if not summaries:
            return "\n(no summary available)"

        own = [s for s in summaries if s.role == DirRole.own]
        external = [s for s in summaries if s.role != DirRole.own]

        lines: list[str] = []

        if own:
            lines.append("\n### Own project directories")
            for s in own:
                tech = ", ".join(s.tech_stack) if s.tech_stack else "—"
                lines.append(f"- **{s.path}/** [{tech}]")
                if s.key_files:
                    lines.append(f"  Entry points: {', '.join(s.key_files[:3])}")
                if s.commands:
                    lines.append(f"  Commands: {', '.join(s.commands[:3])}")

        if external:
            names = ", ".join(s.path for s in external)
            lines.append(f"\n### External/vendored (ignored): {names}")

        return "\n".join(lines)

    def tokens_used(self) -> int:
        """Placeholder — actual token tracking done in _init.py."""
        return 0
