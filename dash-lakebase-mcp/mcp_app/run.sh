#!/bin/bash
# MCP Server for Excel Writeback
# Runs the standalone MCP server at http://localhost:9001

set -e

echo "🤖 Starting MCP Server..."
echo ""
echo "   MCP Endpoint: http://localhost:9001/mcp"
echo "   Health Check: http://localhost:9001/health"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Ensure we are in the mcp_app directory
cd "$(dirname "$0")"

# Sync dependencies if needed (optional, but good for first run)
# uv sync

# Run uvicorn
# We set PYTHONPATH to src to ensure direct import works without install if preferred,
# but uv run with project should handle it.
export PYTHONPATH=$PYTHONPATH:src

uv run python -m uvicorn range_optimizer.backend.mcp_standalone:app \
    --host 0.0.0.0 \
    --port 9001 \
    --reload \
    --reload-dir src/range_optimizer
