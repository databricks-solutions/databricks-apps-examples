"""
MCP (Model Context Protocol) server for inventory intelligence.

Provides AI assistants with tools to query forecasts, optimization results,
and inventory data from the Databricks Lakebase database.
"""

from .server import mcp_server, create_mcp_app

__all__ = ["mcp_server", "create_mcp_app"]

