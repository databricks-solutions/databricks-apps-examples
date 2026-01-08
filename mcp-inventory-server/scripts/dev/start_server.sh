#!/bin/bash
# Start the MCP server locally for development
# Based on: https://github.com/databricks/app-templates/tree/main/mcp-server-hello-world

set -e

echo "🚀 Starting Coles Inventory Intelligence MCP Server..."
echo ""

# Sync dependencies
echo "📦 Syncing dependencies..."
uv sync

# Set environment variables if not already set
export LAKEBASE_INSTANCE_NAME=${LAKEBASE_INSTANCE_NAME:-daveok}
export LAKEBASE_DATABASE=${LAKEBASE_DATABASE:-databricks_postgres}
export LAKEBASE_SCHEMA=${LAKEBASE_SCHEMA:-excel_app}

echo ""
echo "🔧 Configuration:"
echo "   LAKEBASE_INSTANCE_NAME: $LAKEBASE_INSTANCE_NAME"
echo "   LAKEBASE_DATABASE: $LAKEBASE_DATABASE"
echo "   LAKEBASE_SCHEMA: $LAKEBASE_SCHEMA"
echo ""

# Start the server
echo "🌐 Starting server on http://localhost:8000"
echo "   MCP endpoint: http://localhost:8000/mcp"
echo "   API docs: http://localhost:8000/docs"
echo ""

uv run inventory-mcp-server

