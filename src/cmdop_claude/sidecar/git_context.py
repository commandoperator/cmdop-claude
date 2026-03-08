"""GitContextService — classify own vs external git repositories.

Answers: "what code is ours?" before TreeSummarizer runs.

Pipeline:
    collect(root)
      ├── _find_repos()          # find all .git entries (unlimited depth)
      ├── _inspect_all()         # parallel: remote URL, commit history, active dirs
      ├── _classify_all()        # parallel: one LLM call per repo
      └── _merge() → GitContext  # own_top_dirs: set[str]

Cache: .sidecar/git_context.json, keyed by root HEAD SHA.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from ..models.git_context import GitContext, LLMRepoClassification, RepoInfo, RepoRole

if TYPE_CHECKING:
    from sdkrouter import SDKRouter

logger = logging.getLogger(__name__)

# Dirs to skip when walking
_SKIP_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    "dist", "build", ".tox", ".eggs", "*.egg-info",
    "vendor", "third_party", "3rdparty",
    # Django/Rails/uploads — user-uploaded content often contains cloned repos
    "media", "uploads", "storage", "public/uploads",
})

# Bot email patterns — commits from these are excluded from activity scoring
_BOT_EMAIL_RE = re.compile(
    r"(dependabot|renovate|greenkeeper|snyk-bot|github-actions|"
    r"noreply@github|bot@|\.bot@|automation@)",
    re.IGNORECASE,
)

# Max repos to process (safety cap for huge monorepos)
_MAX_REPOS = 50

# LLM prompt templates
_CLASSIFY_SYSTEM = """\
You classify git repositories inside a software project.
Return exactly one of: "own" (root project), "own-submodule" (same org/owner), "external" (third-party/archived).

Hard rules (apply before reasoning):
- path="." → always "own"
- path contains @archive, @sources, @vendor, @backup → always "external"
- remote matches well-known OSS projects (django, react, stripe, kubernetes, etc.) → "external"
- same GitHub org/user as root AND has recent commits → "own-submodule"
- no remote + path looks like a project module → "own-submodule"
- author_count > 10 → strong signal of external/OSS project

When uncertain → return "external". Be conservative.
"""

_CLASSIFY_USER = """\
Root repo remote: {root_remote}

Classify this repository:
  path: {path}
  remote: {remote_url}
  last commit: {last_commit}
  active dirs (recent 90d): {active_dirs}
  unique human authors (recent 30 commits): {author_count}

Respond with JSON: {{"path": "{path}", "role": "own|own-submodule|external", "reason": "one sentence"}}
"""


def _head_sha(repo_path: Path) -> str:
    """Read HEAD SHA from .git/HEAD (fast, no gitpython)."""
    try:
        head_file = repo_path / ".git" / "HEAD"
        if not head_file.exists():
            # Submodule: .git is a file pointing to worktrees
            git_file = repo_path / ".git"
            if git_file.is_file():
                ref = git_file.read_text().strip()
                if ref.startswith("gitdir: "):
                    actual = repo_path / ref[8:]
                    head_file = actual / "HEAD"
        if head_file.exists():
            content = head_file.read_text().strip()
            if content.startswith("ref: "):
                ref_path = repo_path / ".git" / content[5:]
                if ref_path.exists():
                    return ref_path.read_text().strip()[:40]
                return content[5:]  # detached or ref not resolved
            return content[:40]
    except Exception:
        pass
    return ""


def _cache_key(root: Path) -> str:
    """Cache key = SHA256 of root HEAD SHA (fast)."""
    sha = _head_sha(root)
    return hashlib.sha256(sha.encode()).hexdigest()[:16]


def _load_cache(cache_file: Path, expected_key: str) -> GitContext | None:
    """Load cached GitContext if cache key matches."""
    try:
        if not cache_file.exists():
            return None
        data = json.loads(cache_file.read_text())
        if data.get("_cache_key") != expected_key:
            return None
        return GitContext.model_validate(data["context"])
    except Exception:
        return None


def _save_cache(cache_file: Path, key: str, ctx: GitContext) -> None:
    """Save GitContext to cache file."""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"_cache_key": key, "context": ctx.model_dump(mode="json")}
        cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _find_repos(root: Path) -> list[Path]:
    """Find all .git entries (file or dir) recursively, skipping junk dirs."""
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        current = Path(dirpath)
        # Check BEFORE filtering — .git is a hidden dir that we'd otherwise remove
        has_git = ".git" in dirnames or ".git" in filenames
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        if has_git:
            repos.append(current)
    # Sort shallowest first — ensures root repo (".") always survives the cap
    repos.sort(key=lambda p: len(p.parts))
    return repos[:_MAX_REPOS]


def _inspect_sync(repo_path: Path, root: Path) -> RepoInfo:
    """Inspect a single git repo. Returns RepoInfo (sync)."""
    rel = str(repo_path.relative_to(root)) if repo_path != root else "."
    try:
        import git  # type: ignore[import-untyped]

        repo = git.Repo(str(repo_path))
        if repo.bare or not repo.head.is_valid():
            return RepoInfo(path=rel, has_commits=False)

        # Check for shallow clone
        is_shallow = (repo_path / ".git" / "shallow").exists()

        # Remote URL
        remote_url = ""
        try:
            remote_url = repo.remote("origin").url
        except (ValueError, AttributeError):
            pass

        # Last commit date
        last_commit_date = ""
        try:
            last_commit_date = repo.head.commit.committed_datetime.isoformat()
        except Exception:
            pass

        # Author diversity: count unique human authors in recent commits.
        # Works even for shallow clones — provides ownership signal without
        # needing full history. High author count → likely external/OSS project.
        unique_authors: set[str] = set()
        try:
            for commit in repo.iter_commits(max_count=30):
                author_email = getattr(commit.author, "email", "") or ""
                if not _BOT_EMAIL_RE.search(author_email):
                    unique_authors.add(author_email.lower())
        except Exception:
            pass

        # Active dirs: last 90 days OR 50 commits, skip bot commits
        # Skip file-level stats for shallow clones (stats are expensive and unreliable)
        active_files: set[str] = set()
        if not is_shallow:
            cutoff = datetime.now() - timedelta(days=90)
            try:
                for commit in repo.iter_commits(max_count=50):
                    if commit.committed_datetime.replace(tzinfo=None) < cutoff:
                        break
                    # Filter bot commits
                    author_email = getattr(commit.author, "email", "") or ""
                    if _BOT_EMAIL_RE.search(author_email):
                        continue
                    active_files.update(str(k) for k in commit.stats.files.keys())
            except Exception:
                pass

        active_top = sorted({f.split("/")[0] for f in active_files})

        return RepoInfo(
            path=rel,
            remote_url=remote_url,
            last_commit_date=last_commit_date,
            active_top_dirs=active_top[:20],
            has_commits=True,
            is_shallow=is_shallow,
            author_count=len(unique_authors),
        )
    except ImportError:
        logger.debug("gitpython not installed — skipping git inspection")
        return RepoInfo(path=rel)
    except Exception as e:
        logger.debug("Failed to inspect %s: %s", repo_path, e)
        return RepoInfo(path=rel)


async def _inspect_async(repo_path: Path, root: Path) -> RepoInfo:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _inspect_sync, repo_path, root)


def _classify_sync(sdk: "SDKRouter", info: RepoInfo, root_remote: str) -> LLMRepoClassification:
    """Classify a single repo via LLM (sync)."""
    from sdkrouter import Model

    # Hard rules — no LLM needed
    path_lower = info.path.lower()
    if info.path == ".":
        return LLMRepoClassification(path=info.path, role=RepoRole.own, reason="root repo")
    if any(x in path_lower for x in ("@archive", "@sources", "@vendor", "@backup", "@3rdparty")):
        return LLMRepoClassification(path=info.path, role=RepoRole.external, reason="path convention")

    user_msg = _CLASSIFY_USER.format(
        root_remote=root_remote or "(no remote)",
        path=info.path,
        remote_url=info.remote_url or "(no remote)",
        last_commit=info.last_commit_date or "(unknown)",
        active_dirs=", ".join(info.active_top_dirs[:10]) or "(none)",
        author_count=info.author_count,
    )

    for _ in range(3):
        try:
            response = sdk.parse(
                model=Model.cheap(json=True),
                messages=[
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=LLMRepoClassification,
                temperature=0.0,
                max_tokens=256,
            )
            parsed = response.choices[0].message.parsed
            if parsed:
                # Ensure path matches what we sent (LLM might echo it)
                parsed.path = info.path
                return parsed
        except Exception as e:
            logger.debug("Classification failed for %s: %s", info.path, e)

    # Default: external (conservative)
    return LLMRepoClassification(path=info.path, role=RepoRole.external, reason="classification failed")


async def _classify_async(
    sdk: "SDKRouter", info: RepoInfo, root_remote: str
) -> LLMRepoClassification:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _classify_sync, sdk, info, root_remote)


def _merge(
    infos: list[RepoInfo],
    classifications: list[LLMRepoClassification],
    root: Path | None = None,
) -> set[str]:
    """Compute own_top_dirs from classified repos."""
    own_top_dirs: set[str] = set()
    cls_map = {c.path: c for c in classifications}

    for info in infos:
        cls = cls_map.get(info.path)
        if not cls:
            continue
        if cls.role == RepoRole.own:
            # Root repo — its active dirs are the project.
            # Filter to actual directories (active_top_dirs may include files
            # like .gitmodules from git stats).
            for d in info.active_top_dirs:
                if root is not None:
                    if (root / d).is_dir():
                        own_top_dirs.add(d)
                else:
                    # No root available — trust the list as-is
                    own_top_dirs.add(d)
        elif cls.role == RepoRole.own_submodule:
            # Submodule — add its top-level dir to own
            top = info.path.split("/")[0]
            own_top_dirs.add(top)
        # external → ignored

    return own_top_dirs


class GitContextService:
    """Classify own vs external git repositories in a project tree."""

    def __init__(self, sdk: "SDKRouter") -> None:
        self._sdk = sdk

    def collect(self, root: Path, claude_dir: Path | None = None) -> GitContext:
        """Run full git context collection. Uses cache when possible."""
        cache_file = (claude_dir or root / ".claude") / ".sidecar" / "git_context.json"
        cache_key = _cache_key(root)

        cached = _load_cache(cache_file, cache_key)
        if cached:
            logger.debug("GitContextService: cache hit")
            return cached

        logger.debug("GitContextService: scanning %s", root)
        ctx = asyncio.run(self._collect_async(root))

        _save_cache(cache_file, cache_key, ctx)
        return ctx

    async def _collect_async(self, root: Path) -> GitContext:
        repos = _find_repos(root)
        if not repos:
            logger.debug("No git repos found in %s", root)
            return GitContext()

        # Inspect all repos in parallel
        infos = await asyncio.gather(*[_inspect_async(r, root) for r in repos])
        infos = list(infos)

        # Find root remote for org matching
        root_info = next((i for i in infos if i.path == "."), None)
        root_remote = root_info.remote_url if root_info else ""

        # Classify all repos in parallel
        classifications = await asyncio.gather(*[
            _classify_async(self._sdk, info, root_remote)
            for info in infos
        ])
        classifications = list(classifications)

        own_top_dirs = _merge(infos, classifications, root=root)

        tokens_used = 0  # tracked elsewhere

        return GitContext(
            repos=infos,
            classifications=classifications,
            own_top_dirs=own_top_dirs,
            tokens_used=tokens_used,
        )
