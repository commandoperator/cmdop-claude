"""Package documentation indexer.

Orchestrates: collect → LLM synthesis → SQLite FTS5 cache.
Entry point: PackageIndexer.reindex()
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ..models.package_doc import (
    PackageCacheEntry,
    PackageDoc,
    PackageLLMExamples,
    PackageLLMOverview,
    ReindexResult,
    UsageExample,
)
from .package_collector import CollectedPackage, collect, iter_package_dirs

if TYPE_CHECKING:
    from sdkrouter import SDKRouter
    from ..models.cmdop_config import PackageSource


# ── FTS5 schema (same columns as docs_service) ───────────────────────────────

_CREATE_DOCS_TABLE = (
    "CREATE VIRTUAL TABLE docs USING fts5("
    "path, source, title, body, tokenize = 'unicode61')"
)

# ── Prompts ───────────────────────────────────────────────────────────────────

_OVERVIEW_SYSTEM = (
    "You are a TypeScript package documentation specialist. "
    "Given raw source files for an npm package, extract structured documentation. "
    "Be concise and precise. Focus on what developers need to USE this package. "
    "Do not invent information not present in the sources. "
    "For missing info (no install command, no summary), infer from context."
)

_OVERVIEW_USER = """\
Package: {package_name} v{version}

## README
{readme}

## Sub-component READMEs
{sub_readmes_block}

## Main Export Lines (from index.ts files)
{export_lines_block}

---

Generate structured documentation:
- summary: 2-4 sentences describing what this package does and when to use it
- install: the install command (e.g. "pnpm add {package_name}")
- main_exports: for each MAJOR exported name (skip re-exported internals), provide:
  - name: export name
  - kind: "component" | "hook" | "function" | "type" | "class" | "constant" | "other"
  - description: 1-2 sentences what it does
  - import_path: "{package_name}" or "{package_name}/subpath" for sub-entries
  - signature: TypeScript signature if clearly visible, else ""
- keywords: 5-15 search keywords (component names, use cases, tech names)

Rules:
- Hooks start with "use" — always kind="hook"
- React components with JSX — kind="component"
- Skip TypeScript types/interfaces from main_exports unless critical
- Max 20 exports in main_exports (pick most important)
"""

_EXAMPLES_SYSTEM = (
    "You are a TypeScript documentation specialist extracting usage examples from story files. "
    "Story files use a custom `defineStory` format with named export functions showing component usage. "
    "Extract the most illustrative examples."
)

_EXAMPLES_USER = """\
Package: {package_name}

## Story files
{stories_block}

---

Extract usage examples from the story files above.
For each distinct component/function demonstrated, extract up to 3 examples:
- title: short label ("Basic usage", "With variants", "Loading state")
- code: the TSX/TS code — the export function body only, not the whole file wrapper
- component: the component/hook name this example demonstrates

Rules:
- Skip the `Interactive` story (too complex with controls)
- Prefer concise examples (<25 lines)
- Keep JSX as-is, it's the most useful part
- Max 20 examples total
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pkg_index_dir(packages_path: str) -> Path:
    """~/.claude/cmdop/pkg_index/<hash12>/"""
    h = hashlib.sha256(packages_path.encode()).hexdigest()[:12]
    return Path.home() / ".claude" / "cmdop" / "pkg_index" / h


def _first_sentence(text: str) -> str:
    for sep in (".", "\n"):
        idx = text.find(sep)
        if idx > 0:
            return text[:idx].strip()
    return text[:80].strip()


def _chunk_stories(stories: list[tuple[str, str]], max_per_group: int = 15) -> list[list[tuple[str, str]]]:
    groups: list[list[tuple[str, str]]] = []
    for i in range(0, len(stories), max_per_group):
        groups.append(stories[i:i + max_per_group])
    return groups


def _format_stories_block(stories: list[tuple[str, str]]) -> str:
    parts = []
    for rel_path, content in stories:
        parts.append(f"### {rel_path}\n{content}")
    return "\n\n".join(parts)


def _format_export_lines(lines: list[str]) -> str:
    return "\n".join(lines) if lines else "(no export lines found)"


def _format_sub_readmes(sub_readmes: list[tuple[str, str]]) -> str:
    if not sub_readmes:
        return "(none)"
    parts = []
    for rel_path, content in sub_readmes[:5]:  # cap at 5 sub-readmes
        parts.append(f"### {rel_path}\n{content[:1500]}")
    return "\n\n".join(parts)


def _doc_to_overview_body(doc: PackageDoc) -> str:
    """Build FTS5 body for the package overview document."""
    lines = [doc.summary, "", f"Install: {doc.install}", ""]
    if doc.main_exports:
        lines.append("## Exports")
        for ex in doc.main_exports:
            sig = f" — `{ex.signature}`" if ex.signature else ""
            lines.append(f"- **{ex.name}** ({ex.kind}){sig}: {ex.description}")
        lines.append("")
    if doc.keywords:
        lines.append("## Keywords")
        lines.append(", ".join(doc.keywords))
    return "\n".join(lines)


def _example_body(ex: UsageExample) -> str:
    return f"## {ex.title}\n\n```tsx\n{ex.code}\n```"


# ── LLM calls ─────────────────────────────────────────────────────────────────

def _llm_overview(sdk: "SDKRouter", collected: CollectedPackage) -> tuple[PackageLLMOverview, int]:
    from sdkrouter import Model
    user_msg = _OVERVIEW_USER.format(
        package_name=collected.package_name,
        version=collected.version,
        readme=collected.readme[:3000] if collected.readme else "(no README)",
        sub_readmes_block=_format_sub_readmes(collected.sub_readmes),
        export_lines_block=_format_export_lines(collected.export_lines),
    )
    for _ in range(2):
        try:
            resp = sdk.parse(
                model=Model.cheap(json=True),
                messages=[
                    {"role": "system", "content": _OVERVIEW_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=PackageLLMOverview,
                temperature=0.1,
                max_tokens=4096,
            )
            tokens = resp.usage.total_tokens if resp.usage else 0
            parsed = resp.choices[0].message.parsed
            if parsed:
                return parsed, tokens
        except Exception:
            continue
    return PackageLLMOverview(
        summary=_first_sentence(collected.readme) or collected.package_name,
        install=f"pnpm add {collected.package_name}",
    ), 0


def _llm_examples(
    sdk: "SDKRouter", package_name: str, stories: list[tuple[str, str]]
) -> tuple[list[UsageExample], int]:
    from sdkrouter import Model
    all_examples: list[UsageExample] = []
    total_tokens = 0

    for group in _chunk_stories(stories, max_per_group=15):
        user_msg = _EXAMPLES_USER.format(
            package_name=package_name,
            stories_block=_format_stories_block(group),
        )
        for _ in range(2):
            try:
                resp = sdk.parse(
                    model=Model.cheap(json=True),
                    messages=[
                        {"role": "system", "content": _EXAMPLES_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                    response_format=PackageLLMExamples,
                    temperature=0.1,
                    max_tokens=4096,
                )
                tokens = resp.usage.total_tokens if resp.usage else 0
                total_tokens += tokens
                parsed = resp.choices[0].message.parsed
                if parsed:
                    all_examples.extend(parsed.examples)
                break
            except Exception:
                continue

    return all_examples[:20], total_tokens


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _open_fresh_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute(_CREATE_DOCS_TABLE)
    return conn


def _insert_package(conn: sqlite3.Connection, doc: PackageDoc, source_label: str) -> None:
    # Row 1: package overview
    overview_body = _doc_to_overview_body(doc)
    overview_title = f"{doc.package_name} — {_first_sentence(doc.summary)}"
    conn.execute(
        "INSERT INTO docs VALUES (?, ?, ?, ?)",
        (f"packages/{doc.package_dir}", source_label, overview_title, overview_body),
    )

    # Row 2+: per-example documents (grouped by component)
    # Group examples by component name
    by_component: dict[str, list[UsageExample]] = {}
    for ex in doc.examples:
        key = ex.component or ex.title
        by_component.setdefault(key, []).append(ex)

    for component, examples in by_component.items():
        body_parts = []
        for ex in examples:
            body_parts.append(_example_body(ex))
        body = "\n\n".join(body_parts)
        path = f"packages/{doc.package_dir}/{component}"
        title = f"{component} — {doc.package_name}"
        conn.execute(
            "INSERT INTO docs VALUES (?, ?, ?, ?)",
            (path, source_label, title, body),
        )


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache(index_dir: Path) -> dict[str, PackageCacheEntry]:
    cache_path = index_dir / "cache.json"
    if not cache_path.exists():
        return {}
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        result: dict[str, PackageCacheEntry] = {}
        for k, v in raw.items():
            try:
                result[k] = PackageCacheEntry.model_validate(v)
            except Exception:
                pass
        return result
    except Exception:
        return {}


def _save_cache(index_dir: Path, cache: dict[str, PackageCacheEntry]) -> None:
    cache_path = index_dir / "cache.json"
    index_dir.mkdir(parents=True, exist_ok=True)
    data = {k: v.model_dump(mode="json") for k, v in cache.items()}
    cache_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── Main class ────────────────────────────────────────────────────────────────

class PackageIndexer:
    """Indexes TypeScript package documentation into a SQLite FTS5 database."""

    def __init__(self, sdk: "SDKRouter") -> None:
        self._sdk = sdk

    def reindex(
        self,
        packages_root: Path,
        source: "PackageSource",
        force: bool = False,
    ) -> ReindexResult:
        """Rebuild FTS5 index for all packages under packages_root.

        LLM is called only for packages whose fingerprint changed.
        DB is always rebuilt from scratch (fast, ensures consistency).
        """
        index_dir = _pkg_index_dir(str(packages_root))
        db_path = index_dir / "index.db"
        source_label = source.description or str(packages_root)
        exclude = list(source.exclude_dirs)

        cache = _load_cache(index_dir)
        conn = _open_fresh_db(db_path)

        pkg_dirs = iter_package_dirs(packages_root)
        changed: list[str] = []
        unchanged: list[str] = []
        failed: list[str] = []
        total_tokens = 0
        model_used = ""

        for pkg_dir in pkg_dirs:
            pkg_name = pkg_dir.name
            try:
                collected = collect(pkg_dir, exclude)
                cached = cache.get(pkg_name)

                if not force and cached and cached.fingerprint == collected.fingerprint:
                    # Use cached doc — just re-insert into fresh DB
                    _insert_package(conn, cached.doc, source_label)
                    unchanged.append(pkg_name)
                    continue

                # Need LLM synthesis
                overview, tok1 = _llm_overview(self._sdk, collected)
                examples, tok2 = (
                    _llm_examples(self._sdk, collected.package_name, collected.stories)
                    if collected.stories
                    else ([], 0)
                )
                tokens = tok1 + tok2
                total_tokens += tokens

                # Get model name from SDK (best effort)
                if not model_used:
                    try:
                        from sdkrouter import Model
                        model_used = Model.cheap(json=True)
                    except Exception:
                        model_used = "unknown"

                doc = PackageDoc(
                    package_name=collected.package_name,
                    package_dir=collected.pkg_dir,
                    summary=overview.summary,
                    install=overview.install,
                    main_exports=overview.main_exports,
                    examples=examples,
                    keywords=overview.keywords,
                    source_fingerprint=collected.fingerprint,
                )

                cache[pkg_name] = PackageCacheEntry(
                    package_dir=pkg_name,
                    fingerprint=collected.fingerprint,
                    doc=doc,
                    indexed_at=datetime.now(timezone.utc),
                    tokens_used=tokens,
                    model_used=model_used,
                )

                _insert_package(conn, doc, source_label)
                changed.append(pkg_name)

            except Exception as e:
                failed.append(f"{pkg_name}: {e}")

        conn.commit()
        conn.close()
        _save_cache(index_dir, cache)

        return ReindexResult(
            source_path=str(packages_root),
            total=len(pkg_dirs),
            changed=changed,
            unchanged=unchanged,
            failed=failed,
            tokens_used=total_tokens,
            model_used=model_used,
        )

    def index_db_path(self, packages_root: Path) -> Path:
        """Return path to the FTS5 index DB for this packages root."""
        return _pkg_index_dir(str(packages_root)) / "index.db"
