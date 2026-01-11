#!/bin/bash
# Entrypoint for Databricks Apps deployment
set -e

# UI app uses MCP server for all data operations (no direct DB access)
echo "MCP Server URL: ${MCP_SERVER_URL:-<not set>}"

# Databricks Apps expect port 8000 by default
APP_PORT=${APP_PORT:-8000}
echo "Starting Range Optimizer UI on port: $APP_PORT"

# Check for DEV_MODE to enable hot reload
if [ "${DEV_MODE:-false}" = "true" ]; then
    echo "🔥 DEV_MODE enabled - hot reload active!"
    echo "   Changes to .py files will auto-restart the server"
    exec uvicorn range_optimizer.backend.app:app --host 0.0.0.0 --port $APP_PORT --reload --reload-dir range_optimizer
else
    # Run the application (production mode)
    exec uvicorn range_optimizer.backend.app:app --host 0.0.0.0 --port $APP_PORT
fi
