"""Typed model for ~/.claude/cmdop.json — global cmdop-claude configuration."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from .base import CoreModel

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
