"""MCP tools: docs_search, docs_get, docs_list, docs_reindex (4 tools)."""
from __future__ import annotations

from cmdop_claude._config import get_config


def docs_search(query: str) -> str:
    """Search project documentation by keyword.

    Searches bundled docs shipped with cmdop-claude plus any paths configured
    in ~/.claude/cmdop.json → docsPaths. Returns matching file paths with excerpts.

    Supports FTS5 query syntax:
      - "django migration"  — exact phrase
      - django AND test     — both words required
      - migrat*             — prefix match
      - django NOT celery   — exclusion

    Args:
        query: keyword or phrase to search for
    """
    from cmdop_claude.services.docs_service import DocsService
    cfg = get_config()
    svc = DocsService(cfg.cmdop.docs_sources, cfg.cmdop.package_sources)
    results = svc.search(query)
    if not results:
        return f"No results for: {query}"
    lines = [f"Found {len(results)} result(s) for '{query}':", ""]
    for r in results:
        lines.append(f"- {r['path']}  [source: {r['source']}]")
        lines.append(f"  {r['excerpt'][:120].strip()}")
        lines.append("")
    return "\n".join(lines)


def docs_get(path: str) -> str:
    """Read a documentation file by path returned from docs_search or docs_list.

    MDX files are automatically converted to clean Markdown.

    Args:
        path: relative path to the doc file (as returned by docs_search or docs_list)
    """
    from cmdop_claude.services.docs_service import DocsService
    cfg = get_config()
    svc = DocsService(cfg.cmdop.docs_sources, cfg.cmdop.package_sources)
    return svc.get(path)


def docs_list() -> str:
    """List all indexed documentation files grouped by source.

    Shows all available docs from bundled index and any custom sources
    configured in ~/.claude/cmdop.json → docsPaths.
    Use docs_get to read a specific file.
    """
    from cmdop_claude.services.docs_service import DocsService
    cfg = get_config()
    svc = DocsService(cfg.cmdop.docs_sources, cfg.cmdop.package_sources)
    all_docs = svc.list_all()
    if not all_docs:
        return "No documentation indexed. Add docsPaths to ~/.claude/cmdop.json."
    by_source: dict[str, list[str]] = {}
    for doc in all_docs:
        src = doc["source"] or "unknown"
        by_source.setdefault(src, []).append(doc["path"])
    lines = [f"Total: {len(all_docs)} documents", ""]
    for src, paths in by_source.items():
        lines.append(f"## {src} ({len(paths)} docs)")
        for p in paths:
            lines.append(f"  - {p}")
        lines.append("")
    return "\n".join(lines)


def docs_reindex(path: str = "", force: bool = False) -> str:
    """Build or update the package docs index from packagesPaths config.

    Analyzes TypeScript packages: README + story files + exports → LLM synthesis → FTS5 index.
    First run costs ~$0.01 (LLM). Subsequent runs are free for unchanged packages.

    Args:
        path: specific packages dir to reindex (empty = all from packagesPaths config)
        force: re-run LLM for all packages even if unchanged
    """
    from pathlib import Path as _Path
    from cmdop_claude.services.package_indexer import PackageIndexer
    from cmdop_claude.services.sidecar import SidecarService

    cfg = get_config()
    sources = cfg.cmdop.package_sources
    if path:
        sources = [s for s in sources if s.path == path]

    if not sources:
        msg = "No packagesPaths configured."
        if not cfg.cmdop.package_sources:
            msg += ' Add to ~/.claude/cmdop.json: {"packagesPaths": [{"path": "/abs/path/to/packages", "description": "My packages"}]}'
        return msg

    svc = SidecarService(cfg)
    indexer = PackageIndexer(sdk=svc._sdk)

    result_lines: list[str] = []
    for src in sources:
        r = indexer.reindex(_Path(src.path), src, force=force)
        label = src.description or src.path
        status_parts = [f"{r.changed_count}/{r.total} updated"]
        if r.unchanged:
            status_parts.append(f"{len(r.unchanged)} cached")
        if r.failed:
            status_parts.append(f"{len(r.failed)} failed")
        tokens_str = f", {r.tokens_used} tokens" if r.tokens_used else ""
        result_lines.append(f"{label}: {', '.join(status_parts)}{tokens_str}")
        if r.changed:
            result_lines.append(f"  Updated: {', '.join(r.changed)}")
        if r.failed:
            for f_msg in r.failed:
                result_lines.append(f"  Failed: {f_msg}")

    return "\n".join(result_lines) if result_lines else "Nothing to index."


def register(mcp) -> None:
    """Register all docs tools with the FastMCP instance."""
    mcp.tool()(docs_search)
    mcp.tool()(docs_get)
    mcp.tool()(docs_list)
    mcp.tool()(docs_reindex)
