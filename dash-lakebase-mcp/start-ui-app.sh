#!/bin/bash
# Start only the UI App:
#   - UI App:  ports 7002/7003
# Assumes MCP App is running on 7000/7001
# Uses port range 7000-7003 to avoid conflicts with SSH port forwarding (commonly uses 9000+)
#
# Usage:
#   ./start-ui-app.sh          # Normal mode
#   ./start-ui-app.sh --dev    # Hot reload enabled!

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check for --dev flag
DEV_FLAG=""
if [ "$1" = "--dev" ]; then
    DEV_FLAG="--dev"
    echo "🚀 Starting UI App in DEV MODE (hot reload enabled)..."
else
    echo "🚀 Starting UI App only..."
fi
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

# Kill any existing UI session
echo "🧹 Cleaning up old UI session..."
screen -ls | grep "ui-app" | awk '{print $1}' | xargs -I {} screen -X -S {} quit 2>/dev/null || true

echo ""
echo "🎨 Starting UI app (ports 7002/7003)..."
# Use port 7000 (app port) directly for reliability - proxy on 7001 may not work locally
# We assume MCP server is at localhost:7000. If not running, UI might fail to connect but it will start.
screen -dmS ui-app bash -c "cd '$PROJECT_DIR' && export MCP_SERVER_URL='http://localhost:7000' && ./run-databricks-app-local.sh ui_app 7002 7003 daveok $DEV_FLAG > ui-app.log 2>&1"

echo ""
echo "⏳ Waiting for UI app to initialize (up to 90s)..."

# Wait for UI app to be ready (with timeout)
MAX_WAIT=90
WAIT=0
UI_READY=false

while [ $WAIT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:7003/ > /dev/null 2>&1; then
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
    echo "✅ UI app started successfully!"
    if [ -n "$DEV_FLAG" ]; then
        echo "   🔥 Hot reload is ACTIVE - code changes auto-restart the server"
    fi
else
    echo "⚠️  UI app may still be starting. Check logs with:"
    echo "   screen -r ui-app"
fi
echo ""
echo "📍 Access point:"
echo "   UI App:   http://localhost:7003"
echo ""
echo "📊 View logs:"
echo "   tail -f ui-app.log   # View UI app logs"
echo "   (or screen -r ui-app)"
echo ""
if [ -z "$DEV_FLAG" ]; then
    echo "💡 Tip: Run with --dev flag to enable hot reload:"
    echo "   ./start-ui-app.sh --dev"
    echo ""
fi