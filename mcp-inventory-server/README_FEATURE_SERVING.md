# Feature Serving Implementation Guide

This guide explains how to set up and use Feature Serving for stock optimization in the MCP Inventory Server.

## Overview

The system has been enhanced to use **Databricks Feature Serving** instead of dummy feature engineering. This provides:

✅ **Real Features** - Actual demand forecasts, costs, and inventory data  
✅ **Low Latency** - Online tables provide < 10ms feature lookups  
✅ **Consistency** - Same features for training and serving  
✅ **Scalability** - Auto-scaling endpoints handle production load  
✅ **Lineage** - Unity Catalog tracks feature usage  

## Architecture

```
┌─────────────────────┐
│  Forecast Submit    │
│   (Dash App)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   MCP Server        │
│  (Optimization)     │
└──────────┬──────────┘
           │
           ├──────────────────────────────┐
           │                              │
           ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐
│ Feature Serving     │      │  Model Serving      │
│   Endpoint          │      │    Endpoint         │
│                     │      │                     │
│  • Demand Features  │──────▶│  • EOQ Model       │
│  • Cost Features    │      │  • Predictions      │
│  • Inventory State  │      │                     │
│  • Derived Features │      └─────────────────────┘
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Online Tables      │
│  (Low-Latency)      │
│                     │
│  • Demand Online    │
│  • Cost Online      │
│  • Inventory Online │
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Offline Tables     │
│  (Delta Tables)     │
│                     │
│  • Demand Features  │
│  • Cost Features    │
│  • Inventory        │
└─────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install databricks-feature-engineering>=0.13.0
pip install unitycatalog-ai
pip install databricks-sdk>=0.18.0
```

### 2. Run Setup Scripts (in order)

```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/mcp-inventory-server

# Step 1: Create offline feature tables
uv run python scripts/setup_feature_tables.py

# Step 2: Create online tables for low-latency serving
uv run python scripts/setup_online_table.py

# Step 3: Create Unity Catalog functions
uv run python scripts/create_uc_functions.py

# Step 4: Create FeatureSpec
uv run python scripts/create_feature_spec.py

# Step 5: Create Feature Serving endpoint
uv run python scripts/create_feature_serving_endpoint.py
```

### 3. Verify Setup

```bash
# Test the Feature Serving endpoint
uv run python -c "
from scripts.create_feature_serving_endpoint import test_endpoint
test_endpoint()
"
```

Expected output:
```
✅ Feature Serving endpoint test successful!
   Number of records: 2
   Feature columns: ['sell_id', 'avg_daily_demand', 'demand_std', ...]
```

## What Changed

### Before (Dummy Features)

```python
# Old approach in tools.py
base_demand = float(row.get('SHELF_SPACE_CM', 10)) * 10
record = {
    'avg_daily_demand': base_demand,
    'demand_std': base_demand * 0.2,  # Made up!
    'unit_cost': 10.0,                # Hardcoded!
    'selling_price': 20.0,            # Hardcoded!
}
```

### After (Feature Serving)

```python
# New approach in tools.py
feature_response = client.predict(
    endpoint="stock-optimization-features",
    inputs={
        "dataframe_records": [
            {"sell_id": sell_id} for sell_id in sell_ids
        ]
    }
)
features = feature_response.get("outputs", [])
# Real features from Unity Catalog tables!
```

## Feature Tables

### 1. product_demand_features

Demand forecasting features calculated from historical sales:

| Column | Type | Description |
|--------|------|-------------|
| `sell_id` | STRING | Product identifier (PK) |
| `avg_daily_demand` | DOUBLE | Average daily sales |
| `demand_std` | DOUBLE | Standard deviation of demand |
| `total_forecast_30d` | DOUBLE | 30-day forecast |
| `seasonal_factor` | DOUBLE | Seasonality multiplier |
| `trend_factor` | DOUBLE | Trend multiplier |
| `last_updated` | TIMESTAMP | Last refresh time |

### 2. product_cost_features

Cost and pricing features:

| Column | Type | Description |
|--------|------|-------------|
| `sell_id` | STRING | Product identifier (PK) |
| `unit_cost` | DOUBLE | Cost per unit |
| `selling_price` | DOUBLE | Selling price per unit |
| `holding_cost_rate` | DOUBLE | Annual holding cost rate |
| `ordering_cost` | DOUBLE | Fixed ordering cost |
| `last_updated` | TIMESTAMP | Last refresh time |

### 3. current_inventory

Current inventory state:

| Column | Type | Description |
|--------|------|-------------|
| `sell_id` | STRING | Product identifier (PK) |
| `current_stock` | INT | Current stock level |
| `safety_stock` | INT | Safety stock level |
| `last_order_date` | DATE | Last order date |
| `last_updated` | TIMESTAMP | Last refresh time |

## Unity Catalog Functions

### calculate_reorder_urgency

Calculates urgency score (0-1) based on stock levels:

```python
def calculate_reorder_urgency(
    current_stock: float,
    avg_daily_demand: float,
    safety_stock: float
) -> float:
    days_of_stock = current_stock / avg_daily_demand
    if days_of_stock <= 2: return 1.0  # Critical
    elif days_of_stock <= 7: return 0.7  # High
    elif days_of_stock <= 14: return 0.3  # Medium
    else: return 0.0  # No urgency
```

### calculate_lead_time_demand

Estimates demand during lead time:

```python
def calculate_lead_time_demand(
    avg_daily_demand: float,
    lead_time_days: float = 7.0
) -> float:
    return avg_daily_demand * lead_time_days
```

### calculate_profit_margin

Calculates profit margin percentage:

```python
def calculate_profit_margin(
    selling_price: float,
    unit_cost: float
) -> float:
    if selling_price <= 0: return 0.0
    return (selling_price - unit_cost) / selling_price
```

## FeatureSpec Definition

The FeatureSpec combines feature lookups and transformations:

```python
features = [
    # Lookup from online tables
    FeatureLookup(
        table_name="main.excel_app.product_demand_features_online",
        lookup_key="sell_id",
        feature_names=["avg_daily_demand", "demand_std", ...]
    ),
    
    # Derived features using UC functions
    FeatureFunction(
        udf_name="main.excel_app.calculate_reorder_urgency",
        output_name="reorder_urgency",
        input_bindings={
            "current_stock": "current_stock",
            "avg_daily_demand": "avg_daily_demand",
            "safety_stock": "safety_stock"
        }
    ),
]
```

## Updating Features

### Manual Update (SQL)

```sql
-- Update demand features for a product
UPDATE main.excel_app.product_demand_features
SET 
    avg_daily_demand = 75.5,
    demand_std = 15.1,
    last_updated = CURRENT_TIMESTAMP()
WHERE sell_id = 'PROD-001';
```

### Batch Update (Python)

```python
from server import utils
import pandas as pd

# Calculate features from historical sales
sales_query = """
    SELECT 
        sell_id,
        AVG(daily_sales) as avg_daily_demand,
        STDDEV(daily_sales) as demand_std,
        SUM(daily_sales) as total_forecast_30d
    FROM sales_history
    WHERE date >= CURRENT_DATE - INTERVAL 30 DAYS
    GROUP BY sell_id
"""

features_df = pd.read_sql(sales_query, connection)
utils.batch_insert('main.excel_app.product_demand_features', features_df.to_dict('records'), overwrite=True)
```

### Scheduled Refresh (Databricks Job)

Create a Databricks Job that runs daily:

```python
# job_refresh_features.py
from databricks.sdk import WorkspaceClient
from server import utils

def refresh_demand_features():
    """Refresh demand features from sales history"""
    query = """
        INSERT OVERWRITE main.excel_app.product_demand_features
        SELECT 
            sell_id,
            AVG(daily_sales) as avg_daily_demand,
            STDDEV(daily_sales) as demand_std,
            SUM(CASE WHEN date >= CURRENT_DATE - 30 THEN daily_sales ELSE 0 END) as total_forecast_30d,
            1.0 as seasonal_factor,
            1.0 as trend_factor,
            CURRENT_TIMESTAMP() as last_updated
        FROM sales_history
        WHERE date >= CURRENT_DATE - INTERVAL 90 DAYS
        GROUP BY sell_id
    """
    utils.execute_query(query)
    print("✓ Demand features refreshed")

if __name__ == "__main__":
    refresh_demand_features()
```

## Monitoring

### Check Endpoint Status

```bash
# Get endpoint status
databricks serving-endpoints get stock-optimization-features

# View logs
databricks serving-endpoints logs stock-optimization-features
```

### Monitor Feature Freshness

```sql
-- Check feature age
SELECT 
    'demand' as table_name,
    COUNT(*) as records,
    MAX(last_updated) as latest_update,
    MIN(last_updated) as oldest_update
FROM main.excel_app.product_demand_features

UNION ALL

SELECT 
    'cost',
    COUNT(*),
    MAX(last_updated),
    MIN(last_updated)
FROM main.excel_app.product_cost_features

UNION ALL

SELECT 
    'inventory',
    COUNT(*),
    MAX(last_updated),
    MIN(last_updated)
FROM main.excel_app.current_inventory;
```

### Check Optimization Methods Used

```sql
-- See which method was used for recent optimizations
SELECT 
    optimization_method,
    COUNT(*) as count,
    MAX(optimization_timestamp) as latest_use
FROM excel_app.stock_optimization_results
WHERE optimization_timestamp >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY optimization_method
ORDER BY count DESC;
```

Methods:
- `model_serving_with_features` ✅ Best (Feature Serving + Model Serving)
- `model_serving_fallback` ⚠️ OK (Dummy features + Model Serving)
- `fallback_heuristic` ❌ Fallback (Pure EOQ, no ML)

## Troubleshooting

### Feature Serving Returns Empty

1. Check online tables exist and have data:
   ```sql
   SELECT COUNT(*) FROM main.excel_app.product_demand_features_online;
   ```

2. Verify online table is ONLINE:
   ```python
   from databricks.sdk import WorkspaceClient
   w = WorkspaceClient()
   table = w.online_tables.get(name="main.excel_app.product_demand_features_online")
   print(table.status.detailed_state)  # Should be "ONLINE"
   ```

3. Test feature lookup directly:
   ```python
   import mlflow.deployments
   client = mlflow.deployments.get_deploy_client("databricks")
   response = client.predict(
       endpoint="stock-optimization-features",
       inputs={"dataframe_records": [{"sell_id": "PROD-001"}]}
   )
   print(response)
   ```

### Endpoint Not Ready

```bash
# Check status
databricks serving-endpoints get stock-optimization-features

# If stuck, update to restart
databricks serving-endpoints update-config stock-optimization-features \
    --served-entities entity_name=main.excel_app.stock_optimization_features,workload_size=Small
```

### Online Table Sync Issues

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

# Check online table status
table = w.online_tables.get(name="main.excel_app.product_demand_features_online")
print(f"Status: {table.status.detailed_state}")
print(f"Message: {table.status.message}")

# Trigger manual refresh if needed
# (Note: This requires the table to be configured with triggered scheduling)
```

## Cost Optimization

1. **Scale to Zero**: Endpoint scales down when idle
2. **Right-Size**: Start with "Small" workload size
3. **Monitor Usage**: Check endpoint metrics regularly
4. **Batch Updates**: Update features in batches, not per-record

## Next Steps

1. ✅ **Setup Complete** - Feature Serving is ready
2. 📊 **Populate Real Data** - Replace sample features with actual historical analysis
3. ⏰ **Schedule Refresh** - Create daily/hourly jobs to update features
4. 📈 **Monitor Performance** - Track latency, freshness, and accuracy
5. 🚀 **Scale Up** - Increase endpoint size if needed for production load

## References

- [Feature Serving Documentation](https://docs.databricks.com/machine-learning/feature-store/feature-function-serving.html)
- [Online Tables Guide](https://docs.databricks.com/aws/en/notebooks/source/machine-learning/feature-function-serving-online-tables-dbsdk.html)
- [Unity Catalog Functions](https://docs.databricks.com/udf/unity-catalog.html)
- [Model Serving](https://docs.databricks.com/machine-learning/model-serving/index.html)

