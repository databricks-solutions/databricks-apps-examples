#!/bin/bash
set -e

echo "🚀 Deploying ML Notebooks to Databricks"
echo "========================================"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if databricks CLI is installed
if ! command -v databricks &> /dev/null; then
    echo -e "${YELLOW}⚠️  Databricks CLI not found${NC}"
    echo "Install with: pip install databricks-cli"
    exit 1
fi

echo -e "${BLUE}📋 Configuration${NC}"
echo "Catalog: ${CATALOG:-main}"
echo "Schema: ${SCHEMA:-stock_optimization}"
echo ""

# Validate databricks.yml
echo -e "${BLUE}🔍 Validating bundle...${NC}"
databricks bundle validate

# Deploy the bundle
echo -e "${BLUE}📤 Deploying notebooks and jobs...${NC}"
databricks bundle deploy

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "📚 Notebooks deployed to:"
echo "   /Workspace/Users/<your-email>/stock_optimization_ml/"
echo ""
echo "🎯 Jobs created:"
echo "   1. [dev] 00 - Create Feature Tables"
echo "   2. [dev] 01 - Train Stock Optimizer"
echo "   3. [dev] 02 - Deploy Serving Endpoint"
echo "   4. [dev] Full ML Pipeline (runs all 3 in sequence)"
echo ""
echo -e "${BLUE}🚀 To run the full pipeline:${NC}"
echo "   databricks bundle run full_ml_pipeline"
echo ""
echo -e "${BLUE}🚀 To run individual jobs:${NC}"
echo "   databricks bundle run create_feature_tables"
echo "   databricks bundle run train_stock_optimizer"
echo "   databricks bundle run deploy_serving_endpoint"
echo ""
echo -e "${BLUE}📊 View jobs in workspace:${NC}"
echo "   Workflows → Jobs → [dev] Full ML Pipeline"
echo ""
