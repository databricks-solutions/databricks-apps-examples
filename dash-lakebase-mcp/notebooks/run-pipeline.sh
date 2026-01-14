#!/bin/bash
set -e

echo "🎯 Running Full ML Pipeline"
echo "==========================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parse command line arguments
CATALOG="${CATALOG:-main}"
SCHEMA="${SCHEMA:-stock_optimization}"
JOB_NAME="full_ml_pipeline"

# Show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --catalog CATALOG   Unity Catalog name (default: main)"
    echo "  --schema SCHEMA     Schema name (default: stock_optimization)"
    echo "  --job JOB_NAME      Job to run (default: full_ml_pipeline)"
    echo ""
    echo "Available jobs:"
    echo "  - full_ml_pipeline           Run all steps in sequence"
    echo "  - create_feature_tables      Create feature tables only"
    echo "  - train_stock_optimizer      Train model only"
    echo "  - deploy_serving_endpoint    Deploy endpoint only"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run full pipeline"
    echo "  $0 --job train_stock_optimizer       # Train model only"
    echo "  $0 --catalog prod --schema inventory # Use prod catalog"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --catalog)
            CATALOG="$2"
            shift 2
            ;;
        --schema)
            SCHEMA="$2"
            shift 2
            ;;
        --job)
            JOB_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo -e "${BLUE}📋 Configuration${NC}"
echo "Catalog: $CATALOG"
echo "Schema: $SCHEMA"
echo "Job: $JOB_NAME"
echo ""

# Check if bundle is deployed
echo -e "${BLUE}🔍 Checking deployment status...${NC}"
if ! databricks bundle validate &> /dev/null; then
    echo -e "${YELLOW}⚠️  Bundle not deployed yet${NC}"
    echo "Running deployment first..."
    ./deploy.sh
fi

# Run the job
echo -e "${BLUE}🚀 Starting job: $JOB_NAME${NC}"
echo ""

# Run with parameters
databricks bundle run "$JOB_NAME" \
    --var="catalog=$CATALOG" \
    --var="schema=$SCHEMA"

echo ""
echo -e "${GREEN}✅ Job started successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Monitor progress:${NC}"
echo "   1. Open Databricks workspace"
echo "   2. Go to Workflows → Jobs"
echo "   3. Find: [dev] $(echo $JOB_NAME | sed 's/_/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')"
echo ""
echo -e "${BLUE}📝 View run logs:${NC}"
echo "   Click on the running job → View run details"
echo ""
