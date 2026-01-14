#!/bin/bash
# Extend Delta Lake schema with additional tables
# Uses existing catalogs: range_optimizer_catalog and smarter_forecasting

set -e

PYTHON_ENV="/local_disk0/.ephemeral_nfs/envs/pythonEnv-541d323b-2046-471f-bbda-13da364ca150/bin/python"
NOTEBOOK="notebooks/00_extend_delta_schema.py"

echo "=============================================================="
echo "Extending Delta Lake Schema"
echo "=============================================================="
echo ""
echo "Using Python: $PYTHON_ENV"
echo "Notebook: $NOTEBOOK"
echo ""
echo "This will add the following tables to smarter_forecasting.stock_optimization:"
echo "  - dim_store (Store master)"
echo "  - dim_category (Category hierarchy)"
echo "  - dim_brand (Brand master)"
echo "  - fact_sales_weekly (Historical sales)"
echo "  - fact_planogram_current (Current shelf layout)"
echo "  - cfg_range_constraints (Business rules)"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo "📊 Checking existing catalogs..."
$PYTHON_ENV -c "
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
catalogs = list(w.catalogs.list())
print(f'Found {len(catalogs)} catalogs')
for c in catalogs:
    if c.name in ['range_optimizer_catalog', 'smarter_forecasting']:
        print(f'  ✅ {c.name}')
"

echo ""
echo "📋 Checking existing tables in smarter_forecasting.stock_optimization..."
$PYTHON_ENV -c "
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
try:
    tables = list(w.tables.list(catalog_name='smarter_forecasting', schema_name='stock_optimization'))
    print(f'Found {len(tables)} existing tables:')
    for t in tables:
        print(f'  - {t.name}')
except Exception as e:
    print(f'Error: {e}')
"

echo ""
echo "=============================================================="
echo "To run the notebook, use one of these methods:"
echo "=============================================================="
echo ""
echo "Method 1: Upload to Databricks and run via UI"
echo "  databricks workspace import $NOTEBOOK /Users/\$USER/range_optimizer/00_extend_delta_schema.py"
echo ""
echo "Method 2: Run via Databricks CLI"
echo "  databricks notebooks run /Users/\$USER/range_optimizer/00_extend_delta_schema.py \\"
echo "    --cluster-id YOUR_CLUSTER_ID"
echo ""
echo "Method 3: Run via Databricks Jobs API"
echo "  databricks jobs create --json '{...}'"
echo ""
echo "=============================================================="
echo ""
echo "Note: This script verified your catalogs and tables."
echo "      The notebook must be run on a Databricks cluster with Spark."
echo ""
