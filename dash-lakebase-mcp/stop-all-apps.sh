#!/bin/bash
# Stop the Range Optimizer MCP and UI apps on ports 9000-9003

set -e

echo "🛑 Stopping Range Optimizer apps (ports 9000-9003)..."
echo ""

# Stop screen sessions
if command -v screen &> /dev/null; then
    echo "Stopping screen sessions..."
    screen -ls | grep "mcp-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true
    screen -ls | grep "ui-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true
fi

# Kill databricks apps run-local processes on 9000 ports
echo "Killing databricks apps run-local processes..."
pkill -f "databricks apps run-local.*900" || true

# Also kill uvicorn processes that might be running with --reload
echo "Killing uvicorn processes..."
pkill -f "uvicorn.*range_optimizer" || true

# Kill any processes on 9000 range ports
echo "Cleaning up ports 9000-9003..."
for port in 9000 9001 9002 9003; do
    if lsof -ti:$port > /dev/null 2>&1; then
        echo "  Killing process on port $port..."
        kill -9 $(lsof -ti:$port) 2>/dev/null || true
    fi
done

echo ""
echo "✅ All Range Optimizer apps stopped!"
echo ""

# Show remaining processes
echo "Remaining screen sessions:"
screen -ls 2>&1 | grep -v "No Sockets found" || echo "  None"
echo ""
