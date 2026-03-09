"""MCP server for the sidecar — registers all tool domains.

Register globally:
    python -m cmdop_claude.sidecar.hook register
"""
from fastmcp import FastMCP

from .tools import docs_tools, plugin_tools, sidecar_tools

mcp = FastMCP("cmdop-sidecar")

sidecar_tools.register(mcp)
docs_tools.register(mcp)
plugin_tools.register(mcp)

if __name__ == "__main__":
    mcp.run()
