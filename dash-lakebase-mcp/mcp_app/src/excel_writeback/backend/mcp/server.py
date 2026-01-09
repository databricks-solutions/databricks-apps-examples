"""
MCP Server setup for inventory intelligence.

Creates and configures the FastMCP server with all tools registered.
"""

from fastapi import FastAPI, Request
from fastmcp import FastMCP

from .tools import register_tools
from ..logger import logger

# Create the FastMCP server instance
mcp_server = FastMCP(name="inventory-mcp-server")

# Register all tools
register_tools(mcp_server)

# Create the MCP HTTP app once at module load
_mcp_http_app = None


def create_mcp_app() -> FastAPI:
    """
    Create the MCP HTTP application.
    
    Returns a FastAPI app configured for MCP protocol handling.
    Uses a cached instance to ensure tools are registered.
    """
    global _mcp_http_app
    if _mcp_http_app is None:
        _mcp_http_app = mcp_server.http_app()
        logger.info("Created MCP HTTP app with tools registered")
    return _mcp_http_app


def get_mcp_server() -> FastMCP:
    """Get the MCP server instance"""
    return mcp_server

