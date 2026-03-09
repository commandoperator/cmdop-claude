"""Build docs.db — SQLite FTS5 index from a directory of .md/.mdx files.

Used only at publish time via `make sync-docs`. Not imported at runtime.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from cmdop_claude.services.docs.docs_service import DocsService

_CREATE_TABLE = """
CREATE VIRTUAL TABLE docs USING fts5(
    path,
    source,
    title,
    body,
    tokenize = 'unicode61'
)
"""


def _extract_title(text: str) -> str:
    """Extract title from first # heading."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def build_db(src_dir: Path, dst_db: Path, source_label: str = "") -> int:
    """Scan src_dir, convert MDX, write FTS5 index to dst_db.

    Returns number of indexed files.
    """
    dst_db.parent.mkdir(parents=True, exist_ok=True)
    if dst_db.exists():
        dst_db.unlink()

    conn = sqlite3.connect(dst_db)
    conn.execute(_CREATE_TABLE)

    count = 0
    for f in sorted(src_dir.rglob("*")):
        if f.suffix not in {".md", ".mdx"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if f.suffix == ".mdx":
            text = DocsService.mdx_to_md(text)
        title = _extract_title(text) or f.stem
        rel = str(f.relative_to(src_dir))
        conn.execute(
            "INSERT INTO docs VALUES (?, ?, ?, ?)",
            (rel, source_label, title, text),
        )
        count += 1

    conn.commit()
    conn.close()
    return count
