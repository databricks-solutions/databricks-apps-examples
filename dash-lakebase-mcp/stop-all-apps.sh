#!/bin/bash
# Stop the Range Optimizer MCP and UI apps on ports 7000-7003
# Uses port range 7000-7003 to avoid conflicts with SSH port forwarding (commonly uses 9000+)

set -e

echo "🛑 Stopping Range Optimizer apps (ports 7000-7003)..."
echo ""

# Stop screen sessions
if command -v screen &> /dev/null; then
    echo "Stopping screen sessions..."
    screen -ls | grep "mcp-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true
    screen -ls | grep "ui-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true
fi

# Kill databricks apps run-local processes on 7000 ports (more specific pattern)
echo "Killing databricks apps run-local processes..."
pkill -f "databricks apps run-local.*mcp_app.*700" || true
pkill -f "databricks apps run-local.*ui_app.*700" || true

# Also kill uvicorn processes that might be running with --reload
echo "Killing uvicorn processes..."
pkill -f "uvicorn.*range_optimizer.*700" || true

# Kill any processes on 7000 range ports (but be more careful - check if it's our process)
echo "Cleaning up ports 7000-7003..."
for port in 7000 7001 7002 7003; do
    PID=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$PID" ]; then
        # Check if it's a databricks or uvicorn process before killing
        if ps -p $PID -o command= | grep -E "(databricks|uvicorn|range_optimizer)" > /dev/null 2>&1; then
            echo "  Killing process on port $port (PID: $PID)..."
            kill -9 $PID 2>/dev/null || true
        else
            echo "  ⚠️  Port $port is in use by another process (PID: $PID), skipping..."
        fi
    fi
done

echo ""
echo "✅ All Range Optimizer apps stopped!"
echo ""

# Show remaining processes
echo "Remaining screen sessions:"
screen -ls 2>&1 | grep -v "No Sockets found" || echo "  None"
echo ""
