"""Typed model for ~/.claude/cmdop/config.json — global cmdop-claude configuration."""
from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from cmdop_claude.models.base import CoreModel


_LLM_ROUTING_DEFAULTS: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-v3-r1",
        "key_url": "https://openrouter.ai/keys",
        "env_var": "OPENROUTER_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "env_var": "OPENAI_API_KEY",
    },
    "sdkrouter": {
        "base_url": "https://llm.sdkrouter.com/v1",
        "model": "deepseek/deepseek-v3.2",
        "key_url": "https://sdkrouter.com",
        "env_var": "SDKROUTER_API_KEY",
    },
}


class LLMRouting(CoreModel):
    """LLM provider routing configuration.

    mode: "openrouter" | "openai" | "sdkrouter"
    api_key: provider API key (persisted to config.json)
    model: override default model for this mode
    """

    mode: str = Field(default="openrouter", alias="mode")
    api_key: str = Field(default="", alias="apiKey")
    model: str = Field(default="", alias="model")

    model_config = {"populate_by_name": True}

    @property
    def _defaults(self) -> dict[str, str]:
        return _LLM_ROUTING_DEFAULTS.get(self.mode, _LLM_ROUTING_DEFAULTS["openrouter"])

    @property
    def resolved_base_url(self) -> str:
        return self._defaults["base_url"]

    @property
    def resolved_model(self) -> str:
        return self.model or self._defaults["model"]

    @property
    def key_url(self) -> str:
        return self._defaults["key_url"]

    @property
    def env_var(self) -> str:
        return self._defaults["env_var"]


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

    @property
    def resolved_path(self) -> Path:
        """Resolve ~, symlinks and relative segments to an absolute Path."""
        return Path(self.path).expanduser().resolve()



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
CMDOP_JSON_PATH = Path.home() / ".claude" / "cmdop" / "config.json"


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
    """Typed representation of ~/.claude/cmdop/config.json.

    All fields have safe defaults — missing file → all defaults.
    Env vars in Config (pydantic-settings) override these values.
    """

    # LLM routing — provider + key + model (new unified field)
    llm_routing: LLMRouting = Field(
        default_factory=LLMRouting,
        alias="llmRouting",
    )

    # API keys (legacy — kept for backwards compat and sdkrouter internal use)
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

    # Docs sources — bundled docs by default, override via docsPaths in config.json
    # Accepts list[str] (legacy) or list[{path, description}] (new format)
    docs_sources: list[DocsSource] = Field(
        default_factory=_default_docs_sources,
        alias="docsPaths",
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_key(cls, data: object) -> object:
        """Migrate old sdkrouterApiKey → llmRouting if llmRouting not set."""
        if not isinstance(data, dict):
            return data
        if "llmRouting" not in data and "sdkrouterApiKey" in data:
            legacy_key = data["sdkrouterApiKey"]
            if legacy_key and legacy_key != "test-api-key":
                data["llmRouting"] = {"mode": "sdkrouter", "apiKey": legacy_key}
        return data

    @field_validator("docs_sources", mode="before")
    @classmethod
    def coerce_docs_sources(cls, v: object) -> list[DocsSource]:
        return _coerce_docs_sources(v)

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
        """Load from ~/.claude/cmdop/config.json. Returns defaults if missing/invalid."""
        try:
            if CMDOP_JSON_PATH.exists():
                data = json.loads(CMDOP_JSON_PATH.read_text(encoding="utf-8"))
                return cls.model_validate(data)
        except Exception:
            pass
        return cls()

    def save(self) -> None:
        """Write back to ~/.claude/cmdop/config.json (camelCase keys)."""
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

    def set_llm_routing(self, mode: str, api_key: str, model: str = "") -> None:
        """Update llm_routing in-place and persist."""
        routing = LLMRouting.model_validate({"mode": mode, "apiKey": api_key, "model": model})
        object.__setattr__(self, "llm_routing", routing)
        self.save()

    def set_api_key(self, key: str) -> None:
        """Legacy: update sdkrouterApiKey and migrate to llmRouting=sdkrouter."""
        object.__setattr__(self, "sdkrouter_api_key", key)
        self.set_llm_routing("sdkrouter", key)
