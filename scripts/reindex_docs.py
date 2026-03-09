#!/usr/bin/env python
"""Rebuild FTS5 index for all docs_sources configured in ~/.claude/cmdop/config.json.

Usage:
    python scripts/reindex_docs.py
    python scripts/reindex_docs.py --path /custom/docs/path
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cmdop_claude.models.config.cmdop_config import CmdopConfig, DocsSource
from cmdop_claude.services.docs.docs_builder import build_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex docs sources into FTS5 SQLite databases.")
    parser.add_argument("--path", help="Index a single directory instead of all configured sources.")
    parser.add_argument("--label", default="", help="Label for the source (used with --path).")
    args = parser.parse_args()

    if args.path:
        sources = [DocsSource(path=args.path, description=args.label or args.path)]
    else:
        cfg = CmdopConfig.load()
        sources = cfg.docs_sources
        if not sources:
            print("No docs_sources configured in ~/.claude/cmdop/config.json")
            sys.exit(0)

    print(f"Reindexing {len(sources)} docs source(s)...")
    for source in sources:
        src_path = source.resolved_path
        db_path = src_path / "index.db"
        label = source.description or source.path
        if not src_path.exists():
            print(f"  SKIP {source.path} — path does not exist")
            continue
        print(f"  {source.path}", end=" → ", flush=True)
        n = build_db(src_path, db_path, label)
        print(f"{n} files indexed → {db_path}")

    print("Done.")


if __name__ == "__main__":
    main()
