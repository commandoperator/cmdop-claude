"""MCP tools: mcp_list_servers (1 tool)."""
from __future__ import annotations

import json
from pathlib import Path

from cmdop_claude._config import get_config


def mcp_list_servers() -> str:
    """List all MCP servers configured for Claude Code.

    Reads global servers from ~/.claude.json and project servers from .mcp.json.
    Shows server names, commands, and available tools so you know what's accessible.
    Call this when you're unsure what MCP tools are available in the current session.
    """
    lines: list[str] = []

    claude_json = Path.home() / ".claude.json"
    if claude_json.exists():
        try:
            data = json.loads(claude_json.read_text(encoding="utf-8"))
            global_servers = data.get("mcpServers", {})
            if global_servers:
                lines.append("## Global MCP Servers (~/.claude.json)")
                for name, cfg in global_servers.items():
                    if isinstance(cfg, dict):
                        cmd = cfg.get("command", "")
                        args = " ".join(cfg.get("args", []))
                        lines.append(f"- **{name}**: `{(cmd + ' ' + args).strip()}`")
                lines.append("")
        except Exception:
            pass

    cfg = get_config()
    mcp_json = Path(cfg.claude_dir_path).parent / ".mcp.json"
    if mcp_json.exists():
        try:
            data = json.loads(mcp_json.read_text(encoding="utf-8"))
            project_servers = data.get("mcpServers", {})
            if project_servers:
                lines.append("## Project MCP Servers (.mcp.json)")
                for name, srv in project_servers.items():
                    if isinstance(srv, dict):
                        cmd = srv.get("command", "")
                        args = " ".join(srv.get("args", []))
                        lines.append(f"- **{name}**: `{(cmd + ' ' + args).strip()}`")
                lines.append("")
        except Exception:
            pass

    if not lines:
        return "No MCP servers found in ~/.claude.json or .mcp.json."

    lines.insert(0, "# MCP Servers Available to Claude\n")
    lines.append("Note: sidecar tools (sidecar_tasks, sidecar_scan, sidecar_map, docs_search, docs_get, docs_list, skills_list, skills_get, skills_search) are called directly without ToolSearch.")
    return "\n".join(lines)


def register(mcp) -> None:
    """Register all plugin tools with the FastMCP instance."""
    mcp.tool()(mcp_list_servers)
