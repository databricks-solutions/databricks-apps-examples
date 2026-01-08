"""
Main entry point for the Coles Inventory MCP server.

This module provides the main() function that starts the uvicorn server.
It's configured as the entry point in pyproject.toml.

Usage:
    uv run inventory-mcp-server
    uv run inventory-mcp-server --port 8080
"""

import argparse

import uvicorn


def main():
    """
    Start the MCP server using uvicorn.

    Configuration:
        - host: "0.0.0.0" - Binds to all network interfaces
        - port: Configurable via --port argument (default: 8000)
    """
    parser = argparse.ArgumentParser(description="Start the Coles Inventory MCP server")
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to run the server on (default: 8000)"
    )
    args = parser.parse_args()

    print(f"🚀 Starting Coles Inventory Intelligence MCP Server on port {args.port}")
    print(f"📊 MCP endpoint: http://localhost:{args.port}/mcp")
    print(f"📖 API docs: http://localhost:{args.port}/docs")
    
    uvicorn.run(
        "server.app:combined_app",
        host="0.0.0.0",
        port=args.port,
    )


if __name__ == "__main__":
    main()

