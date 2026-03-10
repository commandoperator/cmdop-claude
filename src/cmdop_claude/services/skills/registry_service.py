"""Skills registry service — fetches and caches skills from remote registries."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


# ── Models ────────────────────────────────────────────────────────────────────

class RegistrySkillMeta(BaseModel):
    """Metadata for a skill repository (rawFileUrl for SKILL.md)."""

    model_config = ConfigDict(extra="allow")

    repo_owner: str = Field(default="", alias="repoOwner")
    repo_name: str = Field(default="", alias="repoName")
    directory_path: str = Field(default="", alias="directoryPath")
    raw_file_url: str = Field(default="", alias="rawFileUrl")


class RegistrySkill(BaseModel):
    """A single skill entry from the registry API."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    namespace: str = ""
    description: str = ""
    source_url: str = Field(default="", alias="sourceUrl")
    version: Optional[str] = None  # API returns null
    author: str = ""
    stars: int = 0
    installs: int = 0
    metadata: RegistrySkillMeta = Field(default_factory=RegistrySkillMeta)

    @property
    def display_name(self) -> str:
        return self.name or self.id

    @property
    def skill_md_url(self) -> str:
        return self.metadata.raw_file_url


class RegistryPage(BaseModel):
    """Paginated response from registry API."""

    model_config = ConfigDict(extra="allow")

    skills: list[RegistrySkill] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


# ── Source abstraction ────────────────────────────────────────────────────────

class RegistrySource(Protocol):
    """Protocol for a skills registry source. Implement to add new registries."""

    name: str
    base_url: str

    def search(self, query: str, limit: int, offset: int) -> RegistryPage: ...
    def fetch_skill_md(self, skill: RegistrySkill) -> str: ...


class ClaudePluginsDevSource:
    """Source backed by https://claude-plugins.dev/api/skills."""

    name = "claude-plugins.dev"
    base_url = "https://claude-plugins.dev/api/skills"

    def search(self, query: str = "", limit: int = 100, offset: int = 0) -> RegistryPage:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if query:
            params["q"] = query
        try:
            r = httpx.get(self.base_url, params=params, timeout=10)
            r.raise_for_status()
            return RegistryPage.model_validate(r.json())
        except Exception:
            return RegistryPage()

    def fetch_skill_md(self, skill: RegistrySkill) -> str:
        url = skill.skill_md_url
        if not url:
            return ""
        try:
            r = httpx.get(url, timeout=10, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception:
            return ""


# ── Registry service ──────────────────────────────────────────────────────────

_CACHE_TTL = 300  # seconds


class RegistryService:
    """Aggregates multiple registry sources and installs skills locally.

    Multi-source ready: pass additional RegistrySource implementations to
    the constructor to aggregate results from multiple registries.
    """

    def __init__(
        self,
        skills_dir: Path,
        sources: Optional[list[RegistrySource]] = None,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self._skills_dir = skills_dir
        self._sources: list[RegistrySource] = sources or [ClaudePluginsDevSource()]
        self._cache_dir = cache_dir
        self._mem_cache: dict[str, tuple[float, RegistryPage]] = {}

    def search(
        self,
        query: str = "",
        limit: int = 100,
        offset: int = 0,
        source_name: Optional[str] = None,
    ) -> RegistryPage:
        """Search across all sources (or a specific one) and merge results.

        Results are memory-cached for _CACHE_TTL seconds per (source, query, offset).
        """
        sources = [s for s in self._sources if source_name is None or s.name == source_name]
        merged_skills: list[RegistrySkill] = []
        total = 0

        for source in sources:
            cache_key = f"{source.name}:{query}:{limit}:{offset}"
            now = time.monotonic()
            if cache_key in self._mem_cache:
                ts, page = self._mem_cache[cache_key]
                if now - ts < _CACHE_TTL:
                    merged_skills.extend(page.skills)
                    total += page.total
                    continue

            page = source.search(query=query, limit=limit, offset=offset)
            self._mem_cache[cache_key] = (now, page)
            merged_skills.extend(page.skills)
            total += page.total

        return RegistryPage(skills=merged_skills, total=total, limit=limit, offset=offset)

    def install(self, skill: RegistrySkill, source_name: Optional[str] = None) -> str:
        """Download SKILL.md from registry and install to ~/.claude/skills/<name>/.

        Returns the installed directory name.
        Raises ValueError if SKILL.md cannot be fetched.
        Raises FileExistsError if already installed.
        """
        source = next(
            (s for s in self._sources if source_name is None or s.name == source_name),
            self._sources[0],
        )

        dir_name = skill.id.replace("/", "-").replace(" ", "-").lower()
        dest = self._skills_dir / dir_name
        if dest.exists():
            raise FileExistsError(f"Skill '{dir_name}' is already installed.")

        content = source.fetch_skill_md(skill)
        if not content:
            raise ValueError(f"Could not fetch SKILL.md for '{skill.display_name}'.")

        self._skills_dir.mkdir(parents=True, exist_ok=True)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(content, encoding="utf-8")
        return dir_name

    def is_installed(self, skill: RegistrySkill) -> bool:
        dir_name = skill.id.replace("/", "-").replace(" ", "-").lower()
        return (self._skills_dir / dir_name / "SKILL.md").exists()

    @property
    def source_names(self) -> list[str]:
        return [s.name for s in self._sources]
