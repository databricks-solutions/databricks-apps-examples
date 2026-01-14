#!/bin/bash
# Development server for Excel Writeback Dash App
# Runs the Dash UI at http://localhost:9000

set -e

echo "🚀 Starting Excel Writeback Development Server..."
echo ""
echo "   Dash UI: http://localhost:9000"
echo "   API:     http://localhost:9000/api"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Ensure we are in the ui_app directory
cd "$(dirname "$0")"

uv run python -m uvicorn range_optimizer.backend.app:app \
    --host 0.0.0.0 \
    --port 9000 \
    --reload \
    --reload-dir range_optimizer
