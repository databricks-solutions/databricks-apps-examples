#!/bin/bash
# Start only the UI App:
#   - UI App:  ports 9002/9003
# Assumes MCP App is running on 9001

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Starting UI App only..."
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
echo "🎨 Starting UI app (ports 9002/9003)..."
# We assume MCP server is at localhost:9001. If not running, UI might fail to connect but it will start.
screen -dmS ui-app bash -c "cd '$PROJECT_DIR' && export MCP_SERVER_URL='http://localhost:9001' && ./run-databricks-app-local.sh ui_app 9002 9003 daveok > ui-app.log 2>&1"

echo ""
echo "⏳ Waiting for UI app to initialize (up to 90s)..."

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
    echo "✅ UI app started successfully!"
else
    echo "⚠️  UI app may still be starting. Check logs with:"
    echo "   screen -r ui-app"
fi
echo ""
echo "📍 Access point:"
echo "   UI App:   http://localhost:9003"
echo ""
echo "📊 View logs:"
echo "   tail -f ui-app.log   # View UI app logs"
echo "   (or screen -r ui-app)"
echo ""
