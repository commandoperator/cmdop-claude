"""Docs service — SQLite FTS5 full-text search over bundled and custom docs."""
from __future__ import annotations

import importlib.resources
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import frontmatter  # python-frontmatter — already a project dependency

if TYPE_CHECKING:
    from cmdop_claude.models.config.cmdop_config import DocsSource


class DocsResult:
    """Single search result."""

    __slots__ = ("path", "title", "excerpt", "score", "source")

    def __init__(
        self,
        path: str,
        title: str,
        excerpt: str,
        score: float,
        source: str,
    ) -> None:
        self.path = path
        self.title = title
        self.excerpt = excerpt
        self.score = score
        self.source = source

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "excerpt": self.excerpt,
            "score": self.score,
            "source": self.source,
        }


class DocsEntry:
    """Single entry from list_all()."""

    __slots__ = ("path", "title", "source")

    def __init__(self, path: str, title: str, source: str) -> None:
        self.path = path
        self.title = title
        self.source = source

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "title": self.title, "source": self.source}


class DocsService:
    """Search and retrieve documentation from SQLite FTS5 indexes.

    Each source is either:
    - A .db file  (pre-built FTS5 index, fastest)
    - A directory (built into in-memory FTS5 on demand, legacy fallback)
    """

    EXTENSIONS = {".md", ".mdx"}

    def __init__(self, sources: list[DocsSource]) -> None:
        self._sources = sources

    # ── MDX conversion (static, also used by docs_builder) ───────────

    @staticmethod
    def mdx_to_md(text: str) -> str:
        """Strip JSX/import statements from MDX, return clean Markdown."""
        post = frontmatter.loads(text)
        content: str = post.content
        metadata: dict[str, Any] = post.metadata  # type: ignore[assignment]

        content = re.sub(r"^(import|export)\s+.*$", "", content, flags=re.MULTILINE)
        content = re.sub(
            r"<[A-Z][A-Za-z0-9.]*(?:\s[^>]*)?\s*/>", "", content, flags=re.DOTALL
        )
        prev = None
        while prev != content:
            prev = content
            content = re.sub(
                r"<([A-Z][A-Za-z0-9.]*)(?:\s[^>]*)?>(.+?)</\1>",
                r"\2",
                content,
                flags=re.DOTALL,
            )
        content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.DOTALL)
        content = re.sub(r"\{[^}]*\}", "", content)
        content = re.sub(r"\n{3,}", "\n\n", content)

        header = ""
        title = metadata.get("title", "") if metadata else ""
        description = metadata.get("description", "") if metadata else ""
        if title:
            header = f"# {title}\n\n"
        if description:
            header += f"{description}\n\n"

        return header + content.strip()

    # ── DB connections ────────────────────────────────────────────────

    def _bundled_db_path(self) -> Path | None:
        """Path to docs.db shipped with the package."""
        try:
            ref = importlib.resources.files("cmdop_claude") / "docs" / "docs.db"
            with importlib.resources.as_file(ref) as p:
                return Path(p) if Path(p).exists() else None
        except Exception:
            return None

    @contextmanager
    def _open_db(self, path: Path) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            yield conn
        finally:
            conn.close()

    def _memory_db_for_dir(self, src_dir: Path, label: str) -> sqlite3.Connection:
        """Build an in-memory FTS5 index from a directory of .md/.mdx files."""
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE VIRTUAL TABLE docs USING fts5("
            "path, source, title, body, tokenize = 'unicode61')"
        )
        for f in sorted(src_dir.rglob("*")):
            if f.suffix not in self.EXTENSIONS:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if f.suffix == ".mdx":
                text = self.mdx_to_md(text)
            title = self._extract_title(text) or f.stem
            rel = str(f.relative_to(src_dir))
            conn.execute(
                "INSERT INTO docs VALUES (?, ?, ?, ?)",
                (rel, label, title, text),
            )
        conn.commit()
        return conn

    @staticmethod
    def _extract_title(text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _iter_connections(self) -> Generator[tuple[str, sqlite3.Connection], None, None]:
        """Yield (label, connection) for bundled DB + all configured sources."""
        bundled = self._bundled_db_path()
        if bundled:
            yield "bundled", sqlite3.connect(f"file:{bundled}?mode=ro", uri=True)

        for src in self._sources:
            label = src.description or src.path
            p = Path(src.path).expanduser().resolve()
            if not p.exists():
                continue
            if p.suffix == ".db":
                yield label, sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            elif p.is_dir():
                yield label, self._memory_db_for_dir(p, label)


    # ── Public API ────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """BM25-ranked full-text search across all sources.

        Supports FTS5 query syntax:
          - "django migration"  — exact phrase
          - django AND test     — both words
          - migrat*             — prefix (Porter stemmer also handles inflections)
          - django NOT celery   — exclusion
        """
        items: list[DocsResult] = []
        seen: set[str] = set()

        for label, conn in self._iter_connections():
            try:
                cur = conn.execute(
                    """SELECT path, title,
                              snippet(docs, 3, '[', ']', '...', 20),
                              bm25(docs) AS rank
                       FROM docs
                       WHERE docs MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit),
                )
                for path, title, excerpt, rank in cur.fetchall():
                    key = f"{label}:{path}"
                    if key not in seen:
                        seen.add(key)
                        items.append(
                            DocsResult(
                                path=path,
                                title=title or path,
                                excerpt=excerpt or "",
                                score=-rank,
                                source=label,
                            )
                        )
            except sqlite3.OperationalError:
                # FTS5 syntax error or missing table — skip source
                continue
            finally:
                conn.close()

        items.sort(key=lambda x: -x.score)
        return [r.to_dict() for r in items[:limit]]

    def get(self, path: str) -> str:
        """Retrieve full document body by relative path."""
        for _, conn in self._iter_connections():
            try:
                row = conn.execute(
                    "SELECT body FROM docs WHERE path = ?", (path,)
                ).fetchone()
                if row:
                    return str(row[0])
            except sqlite3.OperationalError:
                continue
            finally:
                conn.close()
        return f"Document not found: {path}"

    def list_all(self) -> list[dict[str, Any]]:
        """List all indexed documents across all sources."""
        items: list[DocsEntry] = []
        seen: set[str] = set()
        for label, conn in self._iter_connections():
            try:
                cur = conn.execute(
                    "SELECT path, title, source FROM docs ORDER BY path"
                )
                for path, title, source in cur.fetchall():
                    key = f"{label}:{path}"
                    if key not in seen:
                        seen.add(key)
                        items.append(
                            DocsEntry(
                                path=path,
                                title=title or path,
                                source=source or label,
                            )
                        )
            except sqlite3.OperationalError:
                continue
            finally:
                conn.close()
        return [e.to_dict() for e in items]
