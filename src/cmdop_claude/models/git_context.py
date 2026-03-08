"""Git context models — repo ownership classification."""
from enum import Enum

from pydantic import BaseModel, Field

from .base import CoreModel


class RepoRole(str, Enum):
    own = "own"
    own_submodule = "own-submodule"
    external = "external"


class RepoInfo(CoreModel):
    """Metadata about a single git repository found in the project tree."""

    path: str  # relative to project root ("." for root, "projects/django" for submodule)
    remote_url: str = ""
    last_commit_date: str = ""
    active_top_dirs: list[str] = Field(default_factory=list)
    has_commits: bool = False
    is_shallow: bool = False
    # Number of unique human authors in recent commits (diversity signal)
    # Used for shallow clone resilience: even shallow clones have author data
    author_count: int = 0


class LLMRepoClassification(BaseModel):
    """LLM classification of a single repository."""

    path: str
    role: RepoRole
    reason: str = ""


class GitContext(CoreModel):
    """Result of GitContextService — passed to TreeSummarizer and init LLM."""

    repos: list[RepoInfo] = Field(default_factory=list)
    classifications: list[LLMRepoClassification] = Field(default_factory=list)
    own_top_dirs: set[str] = Field(default_factory=set)
    tokens_used: int = 0

    def to_prompt_block(self) -> str:
        """Format git context for init LLM prompt."""
        if not self.repos:
            return "(no git repos found)"
        lines: list[str] = []
        cls_map = {c.path: c for c in self.classifications}
        for repo in self.repos:
            cls = cls_map.get(repo.path)
            role = cls.role.value if cls else "unknown"
            remote = repo.remote_url or "(no remote)"
            lines.append(f"- {repo.path}/ [{role}] {remote}")
        return "\n".join(lines)
