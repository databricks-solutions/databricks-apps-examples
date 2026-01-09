# Feature Serving Setup Guide

This guide walks you through setting up Feature Serving for the stock optimization system, replacing dummy feature engineering with real feature lookups from Unity Catalog.

## Architecture Overview

```
Forecast Submission
    ↓
MCP Server Optimization
    ↓
Feature Serving Endpoint → Lookup Features from UC Tables
    ↓
Model Serving Endpoint → Generate Predictions
    ↓
Save Results to Database
```

## Prerequisites

1. **Databricks Workspace** with Feature Engineering enabled
2. **Unity Catalog** access
3. **Python packages:**
   ```bash
   pip install databricks-feature-engineering>=0.13.0
   pip install unitycatalog-ai
   pip install databricks-sdk>=0.18.0
   ```

## Step-by-Step Setup

### Step 1: Create Feature Tables

Run the setup script to create feature tables in Unity Catalog:

```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/mcp-inventory-server

# Set environment variables
export $(grep -v '^#' .env | xargs)

# Run feature tables setup
uv run python scripts/setup_feature_tables.py
```

This creates three feature tables:
- `main.excel_app.product_demand_features` - Demand forecasting features
- `main.excel_app.product_cost_features` - Cost and pricing features
- `main.excel_app.current_inventory` - Current inventory state

### Step 2: Create Unity Catalog Functions

Create UC functions for derived feature calculations:

```bash
uv run python scripts/create_uc_functions.py
```

This creates:
- `main.excel_app.calculate_reorder_urgency` - Urgency score calculation
- `main.excel_app.calculate_lead_time_demand` - Lead time demand estimation
- `main.excel_app.calculate_profit_margin` - Profit margin calculation

### Step 3: Create FeatureSpec

Define the feature specification that combines lookups and transformations:

```bash
uv run python scripts/create_feature_spec.py
```

This creates `main.excel_app.stock_optimization_features` FeatureSpec with:
- Feature lookups from the three tables
- Derived features using UC functions

### Step 4: Create Feature Serving Endpoint

Deploy the Feature Serving endpoint:

```bash
uv run python scripts/create_feature_serving_endpoint.py
```

This creates the `stock-optimization-features` serving endpoint.

**Note:** Endpoint creation takes 3-5 minutes. The script will wait for it to be ready.

### Step 5: Verify Setup

Test that everything is working:

```bash
# Test feature lookup
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

## Feature Tables Schema

### product_demand_features

```sql
CREATE TABLE main.excel_app.product_demand_features (
    sell_id STRING NOT NULL PRIMARY KEY,
    avg_daily_demand DOUBLE,
    demand_std DOUBLE,
    total_forecast_30d DOUBLE,
    seasonal_factor DOUBLE,
    trend_factor DOUBLE,
    last_updated TIMESTAMP
)
```

### product_cost_features

```sql
CREATE TABLE main.excel_app.product_cost_features (
    sell_id STRING NOT NULL PRIMARY KEY,
    unit_cost DOUBLE,
    selling_price DOUBLE,
    holding_cost_rate DOUBLE,
    ordering_cost DOUBLE,
    last_updated TIMESTAMP
)
```

### current_inventory

```sql
CREATE TABLE main.excel_app.current_inventory (
    sell_id STRING NOT NULL PRIMARY KEY,
    current_stock INT,
    safety_stock INT,
    last_order_date DATE,
    last_updated TIMESTAMP
)
```

## Usage in MCP Server

The MCP server `tools.py` has been updated to automatically use Feature Serving:

```python
# 1. Try Feature Serving endpoint first
try:
    feature_response = client.predict(
        endpoint="stock-optimization-features",
        inputs={
            "dataframe_records": [
                {"sell_id": sell_id} for sell_id in sell_ids
            ]
        }
    )
    features = feature_response.get("outputs", [])
    
# 2. Fallback to dummy features if Feature Serving fails
except Exception:
    # Generate dummy features...
```

## Updating Feature Values

### Manual Update

Update feature values directly in the tables:

```python
from server import utils

# Update demand features for a product
update_query = """
UPDATE main.excel_app.product_demand_features
SET avg_daily_demand = %s,
    demand_std = %s,
    last_updated = NOW()
WHERE sell_id = %s
"""

utils.execute_query(update_query, (75.5, 15.1, 'PROD-001'))
```

### Batch Update

Create a scheduled job to refresh features from historical data:

```python
# Example: Calculate demand features from sales history
from databricks.sdk import WorkspaceClient
import pandas as pd

w = WorkspaceClient()

# Query historical sales
sales_df = spark.sql("""
    SELECT 
        sell_id,
        AVG(daily_sales) as avg_daily_demand,
        STDDEV(daily_sales) as demand_std,
        SUM(daily_sales) as total_forecast_30d
    FROM sales_history
    WHERE date >= current_date() - INTERVAL 30 DAYS
    GROUP BY sell_id
""")

# Write to feature table
sales_df.write.mode("overwrite").saveAsTable("main.excel_app.product_demand_features")
```

### Streaming Updates (Advanced)

For real-time feature updates, use Delta Live Tables or Structured Streaming:

```python
# Delta Live Table for continuous feature updates
@dlt.table(
    name="product_demand_features",
    table_properties={"delta.enableChangeDataFeed": "true"}
)
def demand_features():
    return (
        spark.readStream
            .table("sales_stream")
            .groupBy("sell_id", window("timestamp", "1 hour"))
            .agg(
                avg("sales_qty").alias("avg_daily_demand"),
                stddev("sales_qty").alias("demand_std")
            )
    )
```

## Monitoring and Maintenance

### Check Endpoint Status

```bash
# Get endpoint status
databricks serving-endpoints get stock-optimization-features

# View logs
databricks serving-endpoints logs stock-optimization-features
```

### Monitor Feature Freshness

Check when features were last updated:

```sql
SELECT 
    sell_id,
    last_updated,
    DATEDIFF(NOW(), last_updated) as days_since_update
FROM main.excel_app.product_demand_features
WHERE DATEDIFF(NOW(), last_updated) > 7
ORDER BY days_since_update DESC
```

### Scale Endpoint

If you need higher throughput, scale the endpoint:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

w.serving_endpoints.update_config(
    name="stock-optimization-features",
    served_entities=[{
        "entity_name": "main.excel_app.stock_optimization_features",
        "workload_size": "Medium",  # or "Large"
        "scale_to_zero_enabled": True
    }]
)
```

## Cost Optimization

### Scale to Zero

The endpoint is configured with `scale_to_zero_enabled=True`, so it automatically scales down when not in use.

### Right-Size Workload

Start with "Small" and scale up only if needed:
- **Small**: ~100 requests/sec
- **Medium**: ~500 requests/sec  
- **Large**: ~1000+ requests/sec

### Monitor Usage

```python
# Check endpoint metrics
endpoint = w.serving_endpoints.get(name="stock-optimization-features")
print(f"State: {endpoint.state.ready}")
print(f"Last activity: {endpoint.last_updated_timestamp}")
```

## Troubleshooting

### Endpoint Not Ready

```bash
# Check endpoint status
databricks serving-endpoints get stock-optimization-features

# If stuck, restart it
databricks serving-endpoints update stock-optimization-features --workload-size Small
```

### Feature Lookup Returns Empty

1. **Check feature tables have data:**
   ```sql
   SELECT COUNT(*) FROM main.excel_app.product_demand_features;
   ```

2. **Verify sell_id exists:**
   ```sql
   SELECT * FROM main.excel_app.product_demand_features WHERE sell_id = 'PROD-001';
   ```

3. **Check FeatureSpec definition:**
   ```python
   from databricks.feature_engineering import FeatureEngineeringClient
   fe = FeatureEngineeringClient()
   spec = fe.get_feature_spec(name="main.excel_app.stock_optimization_features")
   print(spec)
   ```

### Model Serving Fails

The system has a fallback mechanism that uses EOQ heuristics if Model Serving fails:

```python
# Check which method was used
results = utils.execute_query("""
    SELECT optimization_method, COUNT(*) 
    FROM excel_app.stock_optimization_results 
    GROUP BY optimization_method
""")
```

Methods:
- `model_serving_with_features` - Feature Serving + Model Serving (best)
- `model_serving_fallback` - Dummy features + Model Serving
- `fallback_heuristic` - Pure EOQ calculation (no ML)

## Next Steps

1. **Populate Real Features**: Replace sample data with actual historical analysis
2. **Create Scheduled Job**: Refresh features daily/hourly from sales data
3. **Monitor Performance**: Track feature freshness and endpoint latency
4. **Add More Features**: Enhance with seasonality, promotions, competitor data

## References

- [Databricks Feature Serving Documentation](https://docs.databricks.com/machine-learning/feature-store/feature-function-serving.html)
- [Online Feature Store Guide](https://docs.databricks.com/machine-learning/feature-store/online-feature-store.html)
- [Unity Catalog Functions](https://docs.databricks.com/udf/unity-catalog.html)

