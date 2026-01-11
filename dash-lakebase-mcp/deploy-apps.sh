#!/bin/bash
# Deployment script for Databricks Apps with environment variable injection
# This script handles variable substitution for production deployment

set -e

echo "🚀 Deploying Databricks Apps..."

# Get the MCP server URL from databricks.yml variable
MCP_URL="https://range-opt-mcp-daveok-7405614596482958.18.azure.databricksapps.com"

echo "📦 Deploying range_optimizer_mcp (MCP Server)..."
cd mcp_app
databricks bundle deploy --target dev
databricks apps deploy range-opt-mcp-daveok
databricks apps update range-opt-mcp-daveok
cd ..

echo "📦 Deploying range_optimizer_ui (UI App) with MCP_SERVER_URL=$MCP_URL..."
cd ui_app

# Deploy (MCP_SERVER_URL is already configured in app.yaml)
databricks bundle deploy --target dev
databricks apps deploy range-opt-ui-daveok
databricks apps update range-opt-ui-daveok

cd ..

echo "✅ Deployment complete!"
echo ""
echo "Apps deployed:"
echo "  🤖 MCP Server: https://range-opt-mcp-daveok-7405614596482958.18.azure.databricksapps.com"
echo "  🎨 UI App:     https://range-opt-ui-daveok-<workspace-id>.azure.databricksapps.com"
