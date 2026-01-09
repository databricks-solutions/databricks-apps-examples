# Automatic Feature Serving Setup

The MCP Inventory Server now **automatically sets up Feature Serving** when it starts! 🎉

## What Happens Automatically

When the server starts or when you run your first optimization, it will:

1. ✅ **Check for feature tables** - Looks for demand, cost, and inventory feature tables
2. ✅ **Create missing tables** - Automatically creates them if they don't exist
3. ✅ **Populate with sample data** - Adds initial feature data from your products
4. ✅ **Check Feature Serving endpoint** - Verifies the endpoint is available
5. ✅ **Graceful fallback** - Uses dummy features if Feature Serving isn't ready

## Zero-Configuration Mode

**Just start the server and go!** No manual setup required.

```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/mcp-inventory-server

# Start the server - it handles everything automatically
uv run python -m server.main
```

The first time it runs, you'll see:

```
[FEATURE-SETUP] Initializing Feature Serving...
[FEATURE-SETUP] → Feature tables not found, creating them...
[FEATURE-SETUP] ✓ Feature tables created
[FEATURE-SETUP] ✓ Populated 20 products with initial features
[FEATURE-SETUP] ⚠️  Feature Serving endpoint not available
[FEATURE-SETUP]    For now, using fallback feature generation
[FEATURE-SETUP] ✅ Feature Serving initialized successfully
```

## How It Works

### Lazy Initialization

Feature Serving is initialized **lazily** on first use:
- No startup delays
- First optimization request triggers setup
- Subsequent requests use cached status
- Failed setups automatically use fallback

### Auto-Detection

The system automatically detects:
- ✅ Are feature tables present?
- ✅ Do they have data?
- ✅ Is the Feature Serving endpoint available?
- ✅ Can we query it successfully?

### Smart Fallback

If Feature Serving isn't available, it transparently falls back to:
- Dummy feature generation (just like before)
- No errors or failures
- System continues working
- You can add Feature Serving later

## Upgrade to Full Feature Serving

While the system works out-of-the-box, you'll get **better results** with full Feature Serving:

### Option 1: Quick Setup (5 minutes)

Run these two scripts to enable the full Feature Serving endpoint:

```bash
# Create FeatureSpec
uv run python scripts/create_feature_spec.py

# Create Feature Serving endpoint (takes 3-5 minutes)
uv run python scripts/create_feature_serving_endpoint.py
```

That's it! The app will automatically start using it.

### Option 2: Full Setup with Online Store

For production with low-latency serving:

```bash
# Create UC functions for derived features
uv run python scripts/create_uc_functions.py

# Publish to online store
uv run python scripts/publish_to_online_store.py

# Create FeatureSpec
uv run python scripts/create_feature_spec.py

# Create Feature Serving endpoint
uv run python scripts/create_feature_serving_endpoint.py
```

## Checking Status

### See What's Being Used

Check which optimization method is being used:

```sql
SELECT 
    optimization_method,
    COUNT(*) as count
FROM excel_app.stock_optimization_results
WHERE optimization_timestamp >= CURRENT_DATE - INTERVAL 1 DAY
GROUP BY optimization_method;
```

Results:
- `model_serving_with_features` ✅ **Best** - Using Feature Serving + ML Model
- `model_serving_fallback` ⚠️ **OK** - Using dummy features + ML Model
- `fallback_heuristic` ❌ **Basic** - Using EOQ formula only

### Check Feature Tables

```sql
-- See if feature tables exist and have data
SELECT 
    'demand' as table_name,
    COUNT(*) as records
FROM main.excel_app.product_demand_features

UNION ALL

SELECT 'cost', COUNT(*)
FROM main.excel_app.product_cost_features

UNION ALL

SELECT 'inventory', COUNT(*)
FROM main.excel_app.current_inventory;
```

### Check Endpoint Status

```bash
# Check if Feature Serving endpoint exists
databricks serving-endpoints get stock-optimization-features

# If it exists, you'll see:
# State: READY
```

## Environment Variables

Control the behavior with environment variables:

```bash
# Disable fallback (fail if Feature Serving unavailable)
export FEATURE_SERVING_FALLBACK=false

# Default: true (always use fallback if needed)
export FEATURE_SERVING_FALLBACK=true
```

## Architecture

### Before (Manual Setup)

```
User → Run 5 setup scripts manually → Hope everything works → Use app
```

### After (Auto Setup)

```
User → Start app → Everything works automatically! ✨
                      ↓
                 (Lazy initialization)
                      ↓
                 Feature tables created
                      ↓
                 Check for endpoint
                      ↓
                 Use Feature Serving (if available)
                   or
                 Use fallback (if not)
```

## What Gets Created Automatically

### Feature Tables

Three tables are auto-created in `main.excel_app`:

1. **product_demand_features**
   - `sell_id` (primary key)
   - `avg_daily_demand`, `demand_std`, `total_forecast_30d`
   - `seasonal_factor`, `trend_factor`
   - `last_updated`

2. **product_cost_features**
   - `sell_id` (primary key)
   - `unit_cost`, `selling_price`
   - `holding_cost_rate`, `ordering_cost`
   - `last_updated`

3. **current_inventory**
   - `sell_id` (primary key)
   - `current_stock`, `safety_stock`
   - `last_order_date`, `last_updated`

### Initial Data

Features are populated with sensible defaults:
- `avg_daily_demand`: 50 units/day
- `demand_std`: 10 units (20% variation)
- `unit_cost`: $10
- `selling_price`: $20
- `current_stock`: 100 units
- `safety_stock`: 3 days of demand

**Update these with real data** from your sales history for better results!

## Updating Feature Data

### Replace Sample Data with Real Data

```python
from server import utils
import pandas as pd

# Calculate real demand from sales history
demand_query = """
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

# Load and insert
demand_df = pd.read_sql(demand_query, your_connection)
utils.batch_insert(
    'main.excel_app.product_demand_features',
    demand_df.to_dict('records'),
    overwrite=True
)
```

### Set Up Automated Refresh

Create a Databricks Job that runs daily to refresh features:

```python
# scheduled_feature_refresh.py
from server import utils

def refresh_features():
    # Update demand features from sales
    utils.execute_query("""
        INSERT OVERWRITE main.excel_app.product_demand_features
        SELECT ...  -- Your feature calculation logic
        FROM sales_history
    """)
    
    # Update cost features from pricing
    utils.execute_query("""
        INSERT OVERWRITE main.excel_app.product_cost_features
        SELECT ...
        FROM product_pricing
    """)
    
    # Update inventory from WMS
    utils.execute_query("""
        INSERT OVERWRITE main.excel_app.current_inventory
        SELECT ...
        FROM warehouse_inventory
    """)

if __name__ == "__main__":
    refresh_features()
```

## Benefits of Auto-Setup

✅ **No manual steps** - Just start the server  
✅ **Always works** - Graceful fallback if setup incomplete  
✅ **Self-healing** - Retries Feature Serving on each request  
✅ **Zero config** - Works out of the box  
✅ **Easy upgrade** - Add Feature Serving endpoint anytime  
✅ **Production ready** - Handles failures gracefully  

## Troubleshooting

### Feature Tables Not Creating

Check permissions:
```sql
-- Grant CREATE TABLE permission
GRANT CREATE TABLE ON SCHEMA main.excel_app TO `your-service-principal`;
```

### Want to Force Re-initialization

```python
# In Python/notebook
from server.feature_serving_setup import get_feature_serving_manager

manager = get_feature_serving_manager()
manager._initialization_attempted = False
manager._feature_serving_available = False

# Next request will re-initialize
```

### Check What Happened

```python
# Test the auto-setup
from server.feature_serving_setup import auto_initialize_on_startup

auto_initialize_on_startup()
```

## Comparison: Manual vs Auto

| Aspect | Manual Setup | Auto Setup |
|--------|-------------|------------|
| **Setup Time** | 15-20 minutes | 0 seconds |
| **Steps Required** | 5 scripts to run | 0 (automatic) |
| **First Run** | Fails if not set up | Always works |
| **Error Handling** | Manual debugging | Automatic fallback |
| **Upgradability** | Replace everything | Add incrementally |
| **User Experience** | Complex | Simple |

## Summary

**You don't need to do anything!** The app sets up Feature Serving automatically.

- ✅ Start the server
- ✅ Submit a forecast
- ✅ Get optimizations

Everything else happens behind the scenes.

Want better results? Run the setup scripts later to enable the full Feature Serving endpoint. The app will automatically detect and start using it.

**That's it!** 🎉

