#!/bin/bash
# Generic helper script to run any Databricks app locally with automatic credential injection
# Usage: ./run-databricks-app-local.sh <app_dir> <app_port> <proxy_port> [database_instance]
#
# Examples:
#   ./run-databricks-app-local.sh mcp_app 9000 9001 daveok
#   ./run-databricks-app-local.sh ui_app 8002 8003 daveok
#   ./run-databricks-app-local.sh my_other_app 8004 8005 daveok

set -e

# Parse arguments
APP_DIR="${1:-mcp_app}"
APP_PORT="${2:-9000}"
PROXY_PORT="${3:-9001}"
DB_INSTANCE="${4:-daveok}"

# Validate app directory exists
if [ ! -d "$APP_DIR" ]; then
    echo "❌ Error: App directory '$APP_DIR' not found"
    echo ""
    echo "Usage: $0 <app_dir> <app_port> <proxy_port> [database_instance]"
    echo ""
    echo "Examples:"
    echo "  $0 mcp_app 9000 9001 daveok"
    echo "  $0 ui_app 8002 8003 daveok"
    exit 1
fi

echo "🔍 Fetching database credentials from Databricks..."

# Get database host
if ! PGHOST=$(databricks database get-database-instance "$DB_INSTANCE" --output json 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin)['read_write_dns'])"); then
    echo "⚠️  Warning: Could not fetch database host for instance '$DB_INSTANCE'"
    echo "   The app will start but database features may not work."
    PGHOST=""
else
    echo "✅ PGHOST: $PGHOST"
fi

# Get current user
if ! PGUSER=$(databricks current-user me --output json 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin)['userName'])"); then
    echo "⚠️  Warning: Could not fetch current user"
    PGUSER=""
else
    echo "✅ PGUSER: $PGUSER"
fi

# Database and instance details
PGDATABASE="${PGDATABASE:-databricks_postgres}"
LAKEBASE_INSTANCE_NAME="$DB_INSTANCE"

echo ""
echo "🚀 Starting $APP_DIR locally..."
echo "   App running on:      http://localhost:$APP_PORT"
echo "   Access via proxy at: http://localhost:$PROXY_PORT"
echo ""

# Change to app directory
cd "$APP_DIR"

# Build environment variable arguments
ENV_ARGS=(
    --env "APP_PORT=$APP_PORT"
    --env "PGDATABASE=$PGDATABASE"
    --env "PGSSLMODE=require"
    --env "PGPORT=5432"
    --env "LAKEBASE_INSTANCE_NAME=$LAKEBASE_INSTANCE_NAME"
)

# Add optional variables if they were fetched successfully
if [ -n "$PGHOST" ]; then
    ENV_ARGS+=(--env "PGHOST=$PGHOST")
fi

if [ -n "$PGUSER" ]; then
    ENV_ARGS+=(--env "PGUSER=$PGUSER")
fi

# Check if MCP_SERVER_URL should be set (for UI apps)
if [ -n "$MCP_SERVER_URL" ]; then
    echo "🔗 MCP_SERVER_URL: $MCP_SERVER_URL"
    ENV_ARGS+=(--env "MCP_SERVER_URL=$MCP_SERVER_URL")
fi

# Set environment variable to skip venv replacement prompts
export UV_VENV_CLEAR=1

# Run the app with injected environment variables
databricks apps run-local \
  --prepare-environment \
  --app-port "$APP_PORT" \
  --port "$PROXY_PORT" \
  "${ENV_ARGS[@]}"
