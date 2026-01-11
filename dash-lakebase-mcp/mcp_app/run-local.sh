#!/bin/bash
# Helper script to run the MCP app locally with databricks apps run-local
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

echo ""
echo "🚀 Starting MCP app locally..."
echo "   Access at: http://localhost:9001"
echo ""

# Run the app with injected environment variables
databricks apps run-local \
  --prepare-environment \
  --env "PGHOST=$PGHOST" \
  --env "PGDATABASE=$PGDATABASE" \
  --env "PGUSER=$PGUSER" \
  --env "PGSSLMODE=require" \
  --env "PGPORT=5432" \
  --env "LAKEBASE_INSTANCE_NAME=$LAKEBASE_INSTANCE_NAME"
