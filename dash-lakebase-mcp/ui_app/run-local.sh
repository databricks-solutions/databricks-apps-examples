#!/bin/bash
# Helper script to run the UI app locally with databricks apps run-local
# This script automatically fetches database credentials and starts the app

set -e

echo "🔍 Fetching database credentials from Databricks..."

# Get database host
PGHOST=$(databricks database get-database-instance daveok --output json | python3 -c "import sys, json; print(json.load(sys.stdin)['read_write_dns'])")
echo "✅ PGHOST: $PGHOST"

# Get current user
PGUSER=$(databricks current-user me --output json | python3 -c "import sys, json; print(json.load(sys.stdin)['userName'])")
echo "✅ PGUSER: $PGUSER"

# Database and instance details
PGDATABASE="databricks_postgres"
LAKEBASE_INSTANCE_NAME="daveok"

# Point to LOCAL MCP app (change ports if needed)
# Note: Use port 7000 (app port) directly, not 7001 (proxy port) which may not work locally
# Port range 7000-7003 avoids conflicts with SSH port forwarding (commonly uses 9000+)
export MCP_SERVER_URL="${MCP_SERVER_URL:-http://localhost:7000}"
echo "🔗 MCP_SERVER_URL: $MCP_SERVER_URL"

echo ""
echo "🚀 Starting UI app locally..."
echo "   App running on: http://localhost:8002"
echo "   Access via proxy at: http://localhost:8003"
echo "   (using different ports to avoid conflict with MCP app)"
echo ""

# Run the app with injected environment variables on different ports
databricks apps run-local \
  --prepare-environment \
  --app-port 8002 \
  --port 8003 \
  --env "APP_PORT=8002" \
  --env "PGHOST=$PGHOST" \
  --env "PGDATABASE=$PGDATABASE" \
  --env "PGUSER=$PGUSER" \
  --env "PGSSLMODE=require" \
  --env "PGPORT=5432" \
  --env "LAKEBASE_INSTANCE_NAME=$LAKEBASE_INSTANCE_NAME" \
  --env "MCP_SERVER_URL=$MCP_SERVER_URL"
