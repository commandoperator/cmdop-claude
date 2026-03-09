"""Application configuration — env vars override ~/.claude/cmdop/config.json."""
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._constants import ENV_PREFIX, DEFAULT_CLAUDE_DIR
from cmdop_claude.models.config.cmdop_config import CmdopConfig

# Loaded once at import time — cheap (just reads one JSON file)
_cmdop: CmdopConfig = CmdopConfig.load()


def _default_sdkrouter_key() -> str:
    """env var → llm_routing.api_key → legacy sdkrouterApiKey → empty."""
    routing = _cmdop.llm_routing
    # Check mode-specific env var first
    env_key = os.environ.get(routing.env_var, "")
    if env_key:
        return env_key
    # Then llm_routing.api_key
    if routing.api_key:
        return routing.api_key
    # Legacy fallback: sdkrouterApiKey from config (for old configs not yet migrated)
    return _cmdop.sdkrouter_api_key or ""


def _default_smithery_key() -> str:
    return os.environ.get("CLAUDE_CP_SMITHERY_API_KEY") or _cmdop.smithery_api_key or ""


def _default_sidecar_model() -> str:
    return os.environ.get("CLAUDE_CP_SIDECAR_MODEL") or _cmdop.sidecar_model


def _default_debug() -> bool:
    env = os.environ.get("CMDOP_DEBUG_MODE", "")
    if env:
        return env.lower() in ("1", "true", "yes")
    return _cmdop.debug_mode


class Config(BaseSettings):
    """Runtime configuration. Env vars always win over cmdop.json defaults."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        extra="ignore",
    )

    claude_dir_path: str = Field(
        default=DEFAULT_CLAUDE_DIR,
        description="Path to the .claude directory (project-local)",
    )
    debug_mode: bool = Field(default_factory=_default_debug)
    sdkrouter_api_key: str = Field(
        default_factory=_default_sdkrouter_key,
        description="API key for SDKRouter",
    )
    sidecar_model: str = Field(
        default_factory=_default_sidecar_model,
        description="Model ID for sidecar LLM calls",
    )
    smithery_api_key: str = Field(
        default_factory=_default_smithery_key,
        description="Smithery registry API key (optional)",
    )

    # Global dir — can be overridden via env var CLAUDE_CP_GLOBAL_DIR
    global_dir_override: str = Field(
        default="",
        description="Override global cache dir (default: ~/.claude/cmdop/)",
    )

    @property
    def cmdop(self) -> CmdopConfig:
        """Access to the full typed cmdop.json model."""
        return _cmdop

    @property
    def global_dir(self) -> Path:
        """Global cmdop-claude cache directory."""
        if self.global_dir_override:
            return Path(self.global_dir_override).expanduser()
        return _cmdop.paths.global_dir

    @property
    def plugins_cache_path(self) -> Path:
        return self.global_dir / "plugins_cache.json"


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def configure(**kwargs: object) -> Config:
    global _config
    _config = Config.model_validate(kwargs)
    return _config
