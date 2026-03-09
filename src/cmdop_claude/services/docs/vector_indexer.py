"""Vector indexer — embeds .md files and stores in sqlite-vec for semantic search."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import sqlite_vec

if TYPE_CHECKING:
    from cmdop_claude.services.docs.embed_service import EmbedService

logger = logging.getLogger(__name__)

DIMS = 1536  # text-embedding-3-small dimensions


@dataclass
class VectorResult:
    path: str
    title: str
    score: float  # cosine distance (lower = more similar)
    source: str

    def to_dict(self) -> dict:
        return {"path": self.path, "title": self.title, "score": self.score, "source": self.source}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _encode_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_cache (
            path TEXT PRIMARY KEY,
            sha256 TEXT NOT NULL,
            title TEXT NOT NULL,
            source TEXT NOT NULL
        )
    """)
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS doc_vectors USING vec0(
            path TEXT,
            embedding float[{DIMS}]
        )
    """)
    conn.commit()


class VectorIndexer:
    """Build and search a sqlite-vec index from a directory of .md files."""

    def __init__(self, db_path: Path, embed_svc: EmbedService) -> None:
        self._db_path = db_path
        self._embed = embed_svc

    def build(self, docs_dir: Path, source_label: str, force: bool = False) -> dict:
        """Walk docs_dir, embed each .md, upsert into DB. Returns stats."""
        db_path = self._db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = _open_db(db_path)
        _init_schema(conn)

        # Load existing cache
        cache: dict[str, str] = {}
        for row in conn.execute("SELECT path, sha256 FROM file_cache"):
            cache[row[0]] = row[1]

        md_files = sorted(docs_dir.rglob("*.md"))
        stats = {"total": len(md_files), "updated": 0, "unchanged": 0, "failed": 0}

        # Collect files that need update
        to_embed: list[tuple[str, str, str]] = []  # (rel_path, title, text)
        for f in md_files:
            rel = str(f.relative_to(docs_dir))
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                stats["failed"] += 1
                continue
            sha = _sha256(text)
            if not force and cache.get(rel) == sha:
                stats["unchanged"] += 1
                continue
            title = _extract_title(text) or f.stem
            to_embed.append((rel, title, text))

        if not to_embed:
            conn.close()
            return stats

        logger.info("Embedding %d files from %s...", len(to_embed), docs_dir)

        # Embed in batches
        texts = [t for _, _, t in to_embed]
        try:
            vectors = self._embed.embed(texts)
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            conn.close()
            stats["failed"] += len(to_embed)
            return stats

        # Upsert into DB
        for (rel, title, text), vec in zip(to_embed, vectors):
            sha = _sha256(text)
            try:
                # Remove old vector row if exists
                conn.execute("DELETE FROM doc_vectors WHERE path = ?", (rel,))
                # Insert new vector
                conn.execute(
                    "INSERT INTO doc_vectors(path, embedding) VALUES (?, ?)",
                    (rel, _encode_vector(vec)),
                )
                # Update cache
                conn.execute(
                    "INSERT OR REPLACE INTO file_cache(path, sha256, title, source) VALUES (?,?,?,?)",
                    (rel, sha, title, source_label),
                )
                stats["updated"] += 1
            except Exception as e:
                logger.error("Failed to upsert %s: %s", rel, e)
                stats["failed"] += 1

        conn.commit()
        conn.close()
        logger.info("Vector index updated: %s", stats)
        return stats

    def search(self, query: str, limit: int = 8) -> list[VectorResult]:
        """Semantic search — embed query, find nearest docs."""
        if not self._db_path.exists():
            return []

        try:
            query_vec = self._embed.embed_one(query)
        except Exception as e:
            logger.error("Failed to embed query: %s", e)
            return []

        conn = _open_db(self._db_path)
        try:
            rows = conn.execute(
                """
                SELECT v.path, c.title, c.source, v.distance
                FROM doc_vectors v
                JOIN file_cache c ON v.path = c.path
                WHERE v.embedding MATCH ?
                  AND k = ?
                ORDER BY v.distance
                """,
                (_encode_vector(query_vec), limit),
            ).fetchall()
        except Exception as e:
            logger.error("Vector search failed: %s", e)
            conn.close()
            return []
        conn.close()

        return [
            VectorResult(path=row[0], title=row[1], source=row[2], score=float(row[3]))
            for row in rows
        ]
