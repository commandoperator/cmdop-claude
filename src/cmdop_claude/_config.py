"""Configuration settings for the application."""
import json
import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from ._constants import ENV_PREFIX, DEFAULT_CLAUDE_DIR

_DEFAULT_SDKROUTER_KEY = "test-api-key"
_GLOBAL_CMDOP_CONFIG = Path.home() / ".claude" / "cmdop.json"


def _resolve_sdkrouter_key() -> str:
    """Read SDKROUTER_API_KEY: env var → ~/.claude/cmdop.json → default."""
    if key := os.environ.get("SDKROUTER_API_KEY"):
        return key
    try:
        if _GLOBAL_CMDOP_CONFIG.exists():
            data = json.loads(_GLOBAL_CMDOP_CONFIG.read_text(encoding="utf-8"))
            if key := data.get("sdkrouterApiKey"):
                return key
    except Exception:
        pass
    return _DEFAULT_SDKROUTER_KEY

class Config(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        extra="ignore",
    )

    claude_dir_path: str = Field(
        default=DEFAULT_CLAUDE_DIR,
        description="Path to the .claude directory",
    )
    debug_mode: bool = False
    sdkrouter_api_key: str = Field(
        default_factory=_resolve_sdkrouter_key,
        description="API key for SDKRouter (sidecar LLM backend)",
    )
    sidecar_model: str = Field(
        default="deepseek/deepseek-v3.2",
        description="Model ID for sidecar LLM calls (SDKRouter format)",
    )
    smithery_api_key: str = Field(
        default="",
        description="API key for Smithery registry (optional, skip if empty)",
    )

_config: Optional[Config] = None

def get_config() -> Config:
    """Get current configuration (creates from env if not set)."""
    global _config
    if _config is None:
        _config = Config()
    return _config

def configure(**kwargs) -> Config:
    """Set configuration explicitly."""
    global _config
    _config = Config.model_validate(kwargs)
    return _config
