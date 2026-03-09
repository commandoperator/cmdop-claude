"""MCP and Claude Settings models."""
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from cmdop_claude.models.base import CoreModel


class MCPServerCommand(CoreModel):
    """Command-based MCP server (stdio)."""
    type: Literal["command"] = "command"
    command: str
    args: list[str] = []
    env: dict[str, str] = {}


class MCPServerURL(CoreModel):
    """Remote MCP server (streamable-http)."""
    type: Literal["url"] = "url"
    url: str
    env: dict[str, str] = {}


def _server_discriminator(v: Any) -> str:
    """Discriminate MCP server config: entries with 'url' key → url type, else command."""
    if isinstance(v, dict):
        return v.get("type", "url" if "url" in v else "command")
    return getattr(v, "type", "command")


MCPServerConfig = Annotated[
    Union[
        Annotated[MCPServerCommand, Tag("command")],
        Annotated[MCPServerURL, Tag("url")],
    ],
    Discriminator(_server_discriminator),
]
"""A single MCP server — either command-based or remote URL."""


class MCPConfig(BaseModel):
    """Configuration for MCP servers (.mcp.json or ~/.claude.json).

    Uses extra='allow' because ~/.claude.json contains non-MCP fields
    like numStartups, hasCompletedOnboarding, etc.
    """
    model_config = ConfigDict(extra="allow")

    mcpServers: dict[str, MCPServerConfig] = {}


class ClaudeSettings(BaseModel):
    """Claude project/user settings (settings.json).

    Uses extra='allow' to preserve unknown fields on round-trip.
    """
    model_config = ConfigDict(extra="allow")

    model: Optional[str] = None
    maxTokens: Optional[int] = None
    temperature: Optional[float] = None
