"""Typed model for ~/.claude/cmdop.json — global cmdop-claude configuration."""
from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

from pydantic import Field, field_validator

from cmdop_claude.models.base import CoreModel


class DocsSource(CoreModel):
    """A single documentation source with path and human-readable description.

    type:
      "dir"      — (default) directory of .md/.mdx files, indexed as-is
      "packages" — monorepo packages dir; each sub-package becomes one document
                   combining its README.md + src/index.ts export signatures
    """

    path: str
    description: str = ""
    type: str = "dir"  # "dir" | "packages"

    model_config = {"populate_by_name": True}


class PackageSource(CoreModel):
    """A monorepo packages directory to index for documentation.

    Each immediate subdirectory with a package.json or src/ is treated as one package.
    LLM synthesizes docs from README + stories + export lines.
    Index stored at ~/.claude/cmdop/pkg_index/<hash>/index.db.
    """

    path: str
    description: str = ""
    exclude_dirs: list[str] = Field(
        default_factory=lambda: [
            "@refactoring", "@dev", "@docs", "@sources", ".tmp",
        ]
    )

    model_config = {"populate_by_name": True}


def _default_docs_sources() -> list[DocsSource]:
    """Return bundled docs shipped with the package as the default source."""
    try:
        p = importlib.resources.files("cmdop_claude") / "docs"
        return [DocsSource(path=str(p), description="cmdop-claude bundled docs")]
    except Exception:
        return []


def _coerce_docs_sources(value: object) -> list[DocsSource]:
    """Accept list[str] or list[dict] or list[DocsSource] — all valid in JSON."""
    if not isinstance(value, list):
        return _default_docs_sources()
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(DocsSource(path=item, description=""))
        elif isinstance(item, dict):
            result.append(DocsSource(**item))
        elif isinstance(item, DocsSource):
            result.append(item)
    return result

# Canonical location — never changes
CMDOP_JSON_PATH = Path.home() / ".claude" / "cmdop.json"


class CmdopPaths(CoreModel):
    """Filesystem paths used by cmdop-claude. All resolved at load time."""

    # Global dir: ~/.claude/cmdop/  — shared across all projects
    global_dir: Path = Field(
        default_factory=lambda: Path.home() / ".claude" / "cmdop"
    )

    @property
    def plugins_cache(self) -> Path:
        return self.global_dir / "plugins_cache.json"

    @property
    def git_context_cache(self) -> Path:
        """Per-project git context is stored in .sidecar/, not here.
        This is a fallback path used when claude_dir is unknown."""
        return self.global_dir / "git_context_fallback.json"


class CmdopConfig(CoreModel):
    """Typed representation of ~/.claude/cmdop.json.

    All fields have safe defaults — missing file → all defaults.
    Env vars in Config (pydantic-settings) override these values.
    """

    # API keys
    sdkrouter_api_key: str = Field(default="", alias="sdkrouterApiKey")
    smithery_api_key: str = Field(default="", alias="smitheryApiKey")

    # Model overrides
    sidecar_model: str = Field(
        default="deepseek/deepseek-v3.2", alias="sidecarModel"
    )

    # Paths (serialized as strings in JSON, resolved to Path on load)
    global_dir: str = Field(
        default="", alias="globalDir",
        description="Override for global cache dir. Default: ~/.claude/cmdop/",
    )

    # Docs sources — bundled docs by default, override via docsPaths in cmdop.json
    # Accepts list[str] (legacy) or list[{path, description}] (new format)
    docs_sources: list[DocsSource] = Field(
        default_factory=_default_docs_sources,
        alias="docsPaths",
    )

    # Package sources — monorepo packages dirs, indexed via LLM synthesis
    package_sources: list[PackageSource] = Field(
        default_factory=list,
        alias="packagesPaths",
    )

    @field_validator("docs_sources", mode="before")
    @classmethod
    def coerce_docs_sources(cls, v: object) -> list[DocsSource]:
        return _coerce_docs_sources(v)

    @field_validator("package_sources", mode="before")
    @classmethod
    def coerce_package_sources(cls, v: object) -> list[PackageSource]:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(PackageSource(path=item))
            elif isinstance(item, dict):
                result.append(PackageSource(**item))
            elif isinstance(item, PackageSource):
                result.append(item)
        return result

    @property
    def docs_paths(self) -> list[str]:
        """Convenience accessor — list of paths only (for DocsService)."""
        return [s.path for s in self.docs_sources]

    # Feature flags
    debug_mode: bool = Field(default=False, alias="debugMode")

    model_config = {"populate_by_name": True}

    @property
    def paths(self) -> CmdopPaths:
        if self.global_dir:
            return CmdopPaths(global_dir=Path(self.global_dir).expanduser())
        return CmdopPaths()

    # ── I/O ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> "CmdopConfig":
        """Load from ~/.claude/cmdop.json. Returns defaults if missing/invalid."""
        try:
            if CMDOP_JSON_PATH.exists():
                data = json.loads(CMDOP_JSON_PATH.read_text(encoding="utf-8"))
                return cls.model_validate(data)
        except Exception:
            pass
        return cls()

    def save(self) -> None:
        """Write back to ~/.claude/cmdop.json (camelCase keys)."""
        CMDOP_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(by_alias=True, exclude_defaults=True)
        # Always persist api key even if it's the only field
        if self.sdkrouter_api_key:
            data["sdkrouterApiKey"] = self.sdkrouter_api_key
        existing: dict = {}
        try:
            if CMDOP_JSON_PATH.exists():
                existing = json.loads(CMDOP_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        existing.update(data)
        CMDOP_JSON_PATH.write_text(
            json.dumps(existing, indent=2), encoding="utf-8"
        )

    def set_api_key(self, key: str) -> None:
        """Update sdkrouterApiKey in-place and persist."""
        object.__setattr__(self, "sdkrouter_api_key", key)
        self.save()
