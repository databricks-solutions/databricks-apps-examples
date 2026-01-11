#!/bin/bash
# Deployment script for Databricks Apps
# Deploys both apps using Databricks Asset Bundles from the root directory

set -e

# Ensure we're in the correct directory (where databricks.yml is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Deploying Databricks Apps..."
echo "📂 Working directory: $(pwd)"

# Verify databricks.yml exists
if [ ! -f "databricks.yml" ]; then
    echo "❌ Error: databricks.yml not found"
    exit 1
fi

echo ""
echo "📦 Deploying both apps via bundle..."
echo "   - range_optimizer_mcp (MCP Server)"  
echo "   - range_optimizer_ui (UI App)"
echo ""

# Deploy the bundle (uploads source code)
databricks bundle deploy --target dev

echo ""
echo "🚀 Triggering app deployments..."

# Trigger actual app deployments
databricks bundle run range_optimizer_ui
databricks bundle run range_optimizer_mcp

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Apps deployed:"
echo "  🤖 MCP Server: https://range-opt-mcp-daveok-7405614596482958.18.azure.databricksapps.com"
echo "  🎨 UI App:     https://range-opt-ui-daveok-7405614596482958.18.azure.databricksapps.com"
