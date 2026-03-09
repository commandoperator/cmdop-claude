#!/usr/bin/env python
"""Embed docs into sqlite-vec vector index at ~/.claude/cmdop/vectors.db.

Usage:
    python scripts/embed_docs.py
    python scripts/embed_docs.py --path /custom/docs/path --label my-docs
    python scripts/embed_docs.py --force   # re-embed all files (ignore SHA256 cache)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cmdop_claude.models.config.cmdop_config import CmdopConfig, DocsSource
from cmdop_claude.services.docs.embed_service import EmbedService
from cmdop_claude.services.docs.vector_indexer import VectorIndexer


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed docs into vector index.")
    parser.add_argument("--path", help="Index a single directory instead of all configured sources.")
    parser.add_argument("--label", default="", help="Label for the source (used with --path).")
    parser.add_argument("--force", action="store_true", help="Re-embed all files, ignoring SHA256 cache.")
    args = parser.parse_args()

    cfg = CmdopConfig.load()
    routing = cfg.llm_routing

    if not routing.api_key:
        env_var = routing.env_var
        print(f"No API key configured. Set {env_var} or run `cmdop setup`.")
        sys.exit(1)

    if args.path:
        sources = [DocsSource(path=args.path, description=args.label or args.path)]
    else:
        sources = cfg.docs_sources
        if not sources:
            print("No docs_sources configured in ~/.claude/cmdop/config.json")
            sys.exit(0)

    db_path = Path.home() / ".claude" / "cmdop" / "vectors.db"
    embed_svc = EmbedService(routing)
    indexer = VectorIndexer(db_path=db_path, embed_svc=embed_svc)

    print(f"Embedding {len(sources)} docs source(s) → {db_path}")
    print(f"  Provider: {routing.mode}  Model: text-embedding-3-small")
    if args.force:
        print("  Mode: force (re-embed all)")

    for source in sources:
        src_path = source.resolved_path
        label = source.description or source.path
        if not src_path.exists():
            print(f"  SKIP {source.path} — path does not exist")
            continue
        print(f"  {source.path}", end=" → ", flush=True)
        stats = indexer.build(src_path, source_label=label, force=args.force)
        print(
            f"total={stats['total']} updated={stats['updated']} "
            f"unchanged={stats['unchanged']} failed={stats['failed']}"
        )

    print("Done.")


if __name__ == "__main__":
    main()
