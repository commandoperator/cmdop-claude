"""MCP tools: docs_search, docs_get, docs_list (3 tools)."""
from __future__ import annotations

from cmdop_claude._config import get_config


def docs_search(query: str) -> str:
    """Search project documentation by keyword.

    Searches bundled docs shipped with cmdop-claude plus any paths configured
    in ~/.claude/cmdop/config.json → docsPaths. Returns matching file paths with excerpts.

    Supports FTS5 query syntax:
      - "django migration"  — exact phrase
      - django AND test     — both words required
      - migrat*             — prefix match
      - django NOT celery   — exclusion

    Args:
        query: keyword or phrase to search for
    """
    from cmdop_claude.services.docs.docs_service import DocsService
    cfg = get_config()
    svc = DocsService(cfg.cmdop.docs_sources)
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
    from cmdop_claude.services.docs.docs_service import DocsService
    cfg = get_config()
    svc = DocsService(cfg.cmdop.docs_sources)
    return svc.get(path)


def docs_list() -> str:
    """List all indexed documentation files grouped by source.

    Shows all available docs from bundled index and any custom sources
    configured in ~/.claude/cmdop/config.json → docsPaths.
    Use docs_get to read a specific file.
    """
    from cmdop_claude.services.docs.docs_service import DocsService
    cfg = get_config()
    svc = DocsService(cfg.cmdop.docs_sources)
    all_docs = svc.list_all()
    if not all_docs:
        return "No documentation indexed. Add docsPaths to ~/.claude/cmdop/config.json."
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


def docs_semantic_search(query: str, limit: int = 8) -> str:
    """Semantic vector search over documentation using embeddings.

    Finds conceptually similar documentation even when keywords don't match.
    Requires the vector index to be built first with `make embed-docs`.

    Results are ranked by cosine similarity (lower distance = more relevant).

    Args:
        query: natural language description of what you're looking for
        limit: max number of results to return (default 8)
    """
    from pathlib import Path

    from cmdop_claude.services.docs.embed_service import EmbedService
    from cmdop_claude.services.docs.vector_indexer import VectorIndexer

    cfg = get_config()
    db_path = Path.home() / ".claude" / "cmdop" / "vectors.db"
    embed_svc = EmbedService(cfg.cmdop.llm_routing)
    indexer = VectorIndexer(db_path=db_path, embed_svc=embed_svc)
    results = indexer.search(query, limit=limit)
    if not results:
        return (
            f"No semantic results for: {query}\n"
            "Run `make embed-docs` to build the vector index first."
        )
    lines = [f"Found {len(results)} result(s) for '{query}':", ""]
    for r in results:
        lines.append(f"- {r.path}  [source: {r.source}, score: {r.score:.4f}]")
        lines.append(f"  {r.title}")
        lines.append("")
    return "\n".join(lines)


def register(mcp) -> None:
    """Register all docs tools with the FastMCP instance."""
    mcp.tool()(docs_search)
    mcp.tool()(docs_get)
    mcp.tool()(docs_list)
    mcp.tool()(docs_semantic_search)
