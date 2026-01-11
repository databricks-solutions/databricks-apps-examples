#!/bin/bash
# Entrypoint for Databricks Apps deployment
set -e

# Debug: Print database environment variables (Databricks injects these automatically)
echo "Database configuration:"
echo "  PGHOST: ${PGHOST:-<not set>}"
echo "  PGDATABASE: ${PGDATABASE:-<not set>}"
echo "  PGUSER: ${PGUSER:-<not set>}"
echo "  PGPORT: ${PGPORT:-5432}"
echo "  PGSSLMODE: ${PGSSLMODE:-require}"

# Databricks Apps expect port 8000 by default
APP_PORT=${APP_PORT:-8000}
echo "Starting app on port: $APP_PORT"

# Run the application
exec uvicorn range_optimizer.backend.app:app --host 0.0.0.0 --port $APP_PORT
