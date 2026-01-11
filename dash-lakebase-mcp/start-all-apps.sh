#!/bin/bash
# Start both Range Optimizer apps:
#   - MCP App: ports 9000/9001
#   - UI App:  ports 9002/9003
# Does not touch any external services on port 9000

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Starting Range Optimizer apps..."
echo ""

# Check if screen is available
if ! command -v screen &> /dev/null; then
    echo "⚠️  'screen' is not installed. Installing via homebrew..."
    brew install screen || {
        echo "❌ Failed to install screen. Please install it manually:"
        echo "   brew install screen"
        exit 1
    }
fi

# Kill any existing sessions
echo "🧹 Cleaning up old sessions..."
screen -ls | grep "mcp-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true
screen -ls | grep "ui-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true

echo ""
echo "📦 Starting MCP app (ports 9000/9001)..."
screen -dmS mcp-app bash -c "cd '$PROJECT_DIR' && ./run-databricks-app-local.sh mcp_app 9000 9001 daveok > mcp-app.log 2>&1"

# Wait for MCP app first
echo "⏳ Waiting for MCP app to initialize (up to 60s)..."
MCP_WAIT=0
while [ $MCP_WAIT -lt 60 ]; do
    if curl -s http://localhost:9001/ > /dev/null 2>&1; then
        echo "   ✅ MCP app ready"
        break
    fi
    sleep 5
    MCP_WAIT=$((MCP_WAIT + 5))
    echo "   ... MCP still starting ($MCP_WAIT s)"
done

echo ""
echo "🎨 Starting UI app (ports 9002/9003)..."
screen -dmS ui-app bash -c "cd '$PROJECT_DIR' && export MCP_SERVER_URL='http://localhost:9001' && ./run-databricks-app-local.sh ui_app 9002 9003 daveok > ui-app.log 2>&1"

echo ""
echo "⏳ Waiting for UI app to initialize (up to 90s)..."
echo "   Note: First startup can take longer due to package installation."

# Wait for UI app to be ready (with timeout)
MAX_WAIT=90
WAIT=0
UI_READY=false

while [ $WAIT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:9003/ > /dev/null 2>&1; then
        UI_READY=true
        echo "   ✅ UI app ready"
        break
    fi
    sleep 5
    WAIT=$((WAIT + 5))
    echo "   ... UI still starting ($WAIT s)"
done

echo ""
if [ "$UI_READY" = true ]; then
    echo "✅ Both apps started successfully!"
else
    echo "⚠️  UI app may still be starting. Check logs with:"
    echo "   screen -r ui-app"
fi
echo ""
echo "📍 Access points:"
echo "   MCP App:  http://localhost:9001"
echo "   UI App:   http://localhost:9003"
echo ""
echo "ℹ️  Note: Port 9000 is not touched by these scripts."
echo ""
echo "📊 View logs:"
echo "   tail -f mcp-app.log  # View MCP app logs"
echo "   tail -f ui-app.log   # View UI app logs"
echo "   (or screen -r mcp-app / screen -r ui-app)"
echo ""
echo "🛑 Stop all apps:"
echo "   ./stop-all-apps.sh"
echo ""
echo "📋 List running sessions:"
echo "   screen -ls"
echo ""

# Wait a moment and show screen list
sleep 2
echo "🔍 Running sessions:"
screen -ls 2>&1 | grep -E "mcp-app|ui-app" || echo "Starting up..."
