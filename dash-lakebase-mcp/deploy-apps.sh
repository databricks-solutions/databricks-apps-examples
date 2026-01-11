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
cd ..

echo "📦 Deploying range_optimizer_ui (UI App) with MCP_SERVER_URL=$MCP_URL..."
cd ui_app

# Create temporary app.yaml with MCP_SERVER_URL injected
TEMP_APP_YAML=$(mktemp)
cat app.yaml | sed "s|- name: MCP_SERVER_URL|- name: MCP_SERVER_URL\n    value: \"$MCP_URL\"|" > "$TEMP_APP_YAML"

# Backup original and use temp
mv app.yaml app.yaml.bak
mv "$TEMP_APP_YAML" app.yaml

# Deploy
databricks bundle deploy --target dev

# Restore original
mv app.yaml.bak app.yaml

cd ..

echo "✅ Deployment complete!"
echo ""
echo "Apps deployed:"
echo "  🤖 MCP Server: https://range-opt-mcp-daveok-7405614596482958.18.azure.databricksapps.com"
echo "  🎨 UI App:     https://range-opt-ui-daveok-<workspace-id>.azure.databricksapps.com"
