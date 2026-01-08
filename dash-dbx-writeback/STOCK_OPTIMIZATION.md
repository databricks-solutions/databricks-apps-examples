# Stock Optimization Feature

## Overview

The Stock Optimization feature uses a traditional ML model based on Economic Order Quantity (EOQ) theory to optimize inventory levels. The model calculates:

- **Optimal Order Quantity**: The most cost-effective order size
- **Safety Stock**: Buffer inventory to maintain service levels
- **Reorder Point**: When to place new orders
- **Cost Analysis**: Holding costs, ordering costs, and profitability

## Architecture

The implementation uses a **hybrid approach**:

1. **MLflow Model Serving** (Production): The model is deployed to Databricks MLflow Model Serving endpoint
2. **Local Fallback** (Development): Falls back to local computation if the endpoint is unavailable

```
┌─────────────────┐
│  Dash App       │
└────────┬────────┘
         │
         v
┌─────────────────────────┐
│ HybridStockOptimizer    │
└────────┬────────────────┘
         │
    ┌────┴────┐
    │         │
    v         v
┌─────────┐ ┌──────────┐
│ MLflow  │ │ Local    │
│ Endpoint│ │ Fallback │
└─────────┘ └──────────┘
```

## Model Details

### Algorithm: Economic Order Quantity (EOQ)

**EOQ Formula:**
```
EOQ = √((2 × D × S) / (H × C))
```

Where:
- D = Annual demand
- S = Ordering cost per order
- H = Holding cost rate (as % of unit cost)
- C = Unit cost

**Safety Stock Formula:**
```
Safety Stock = Z × σ × √L
```

Where:
- Z = Safety factor (z-score for service level, e.g., 1.65 for 95%)
- σ = Standard deviation of demand
- L = Lead time in days

**Reorder Point Formula:**
```
ROP = (Average Daily Demand × Lead Time) + Safety Stock
```

### Model Configuration

Default configuration:
- Holding cost rate: 25% annually
- Ordering cost: $50 per order
- Lead time: 7 days
- Service level: 95%
- Safety factor: 1.65 (corresponds to 95% service level)
- Max storage capacity: 10,000 units

## Deployment Guide

### Step 1: Deploy Model to MLflow

Run the deployment script:

```bash
cd /path/to/dash-dbx-writeback
uv run python deploy_model_to_mlflow.py
```

This will:
1. Create an MLflow model wrapper
2. Log the model to MLflow
3. Register the model in the model registry
4. Provide instructions for creating a serving endpoint

### Step 2: Create Serving Endpoint

#### Option A: Using Databricks UI

1. Navigate to your Databricks workspace
2. Go to **Machine Learning** → **Serving**
3. Click **"Create serving endpoint"**
4. Configure:
   - **Name**: `stock-optimization-model`
   - **Model**: Select `stock-optimization-model` from registry
   - **Model version**: Latest
   - **Compute**: Small (or appropriate size)
   - **Scale to zero**: Enabled (recommended for cost savings)
5. Click **"Create"**
6. Wait 5-10 minutes for endpoint to become "Ready"

#### Option B: Using Databricks CLI

```bash
databricks serving-endpoints create \
  --name stock-optimization-model \
  --config '{
    "served_entities": [{
      "entity_name": "stock-optimization-model",
      "entity_version": "1",
      "workload_size": "Small",
      "scale_to_zero_enabled": true
    }]
  }'
```

### Step 3: Verify Endpoint

Check endpoint status:

```bash
databricks serving-endpoints get --name stock-optimization-model
```

Or check in the UI under **Machine Learning → Serving**.

## Usage

### In the Dash Application

1. Navigate to **Stock Optimization** page
2. Click **"Run Stock Optimization"**
3. The app will:
   - Generate forecast data (or use real data from database)
   - Call the MLflow endpoint (or use local fallback)
   - Display optimization results in table and charts
4. Review the results:
   - **Summary cards**: Key metrics at a glance
   - **Charts**: Visual analysis of stock levels, costs, and profitability
   - **Detailed table**: Full optimization results
5. Export results using **"Download Results CSV"**

### Testing Locally

The app automatically falls back to local computation if the MLflow endpoint is unavailable. This is useful for:
- Development and testing
- Environments without Databricks access
- Endpoint debugging

To force local mode, you can modify `HybridStockOptimizer` initialization in the callbacks:

```python
optimizer = HybridStockOptimizer(
    endpoint_name="stock-optimization-model",
    use_fallback=True  # Set to False to disable fallback
)
```

## API Reference

### Input Data Format

The model expects a DataFrame with these columns:

| Column | Type | Description |
|--------|------|-------------|
| `SELL_ID` | string | Unique product identifier |
| `PRODUCT_NAME` | string | Product name |
| `AVG_DAILY_DEMAND` | float | Average daily demand units |
| `DEMAND_STD` | float | Standard deviation of demand |
| `UNIT_COST` | float | Cost per unit |
| `SELLING_PRICE` | float | Selling price per unit |

### Output Data Format

The model returns a DataFrame with these columns:

| Column | Type | Description |
|--------|------|-------------|
| `SELL_ID` | string | Product identifier |
| `PRODUCT_NAME` | string | Product name |
| `AVG_DAILY_DEMAND` | float | Average daily demand |
| `OPTIMAL_ORDER_QTY` | float | Optimal order quantity (EOQ) |
| `SAFETY_STOCK` | float | Safety stock units |
| `REORDER_POINT` | float | Reorder point units |
| `MAX_STOCK_LEVEL` | float | Maximum stock level |
| `ANNUAL_HOLDING_COST` | float | Annual holding cost ($) |
| `ANNUAL_ORDERING_COST` | float | Annual ordering cost ($) |
| `TOTAL_ANNUAL_COST` | float | Total annual cost ($) |
| `EXPECTED_ANNUAL_REVENUE` | float | Expected annual revenue ($) |
| `EXPECTED_ANNUAL_PROFIT` | float | Expected annual profit ($) |
| `TURNOVER_RATE` | float | Inventory turnover rate |
| `SERVICE_LEVEL` | float | Target service level (0-1) |

## Monitoring

### Endpoint Metrics

Monitor your endpoint in Databricks:
- Go to **Machine Learning → Serving → [your-endpoint]**
- View metrics:
  - Request latency
  - Request rate
  - Error rate
  - Model version

### Application Logs

The application logs optimization activity:

```
[timestamp] → Initializing hybrid stock optimizer (MLflow + fallback)...
[timestamp] ✓ Optimizer initialized
[timestamp] → Running optimization algorithm...
[timestamp] ✓ Optimization complete using 'mlflow' method for 10 products
[timestamp] → Generating summary statistics...
[timestamp] ✓ Summary generated
```

Method can be:
- `mlflow`: Successfully used MLflow endpoint
- `fallback`: Used local computation
- `error`: Both failed (rare)

## Troubleshooting

### MLflow Endpoint Not Found

**Error**: `Endpoint unavailable: [404] Not Found`

**Solution**:
1. Verify endpoint exists: Check **Machine Learning → Serving**
2. Verify endpoint name matches in code (default: `stock-optimization-model`)
3. Ensure endpoint is in "Ready" state
4. Check you have permission to access the endpoint

### Authentication Errors

**Error**: `[401] Unauthorized`

**Solution**:
1. Verify Databricks CLI is configured: `databricks auth profiles`
2. Re-authenticate: `databricks configure --token`
3. Check your token has not expired

### Model Serving Errors

**Error**: `[500] Internal Server Error`

**Solution**:
1. Check endpoint logs in Databricks UI
2. Verify model is properly registered
3. Try redeploying the model
4. Check compute resources are sufficient

### Fallback Always Used

**Symptom**: Logs show `'fallback'` method every time

**Solution**:
1. Check MLflow endpoint status
2. Verify endpoint URL is correct
3. Check network connectivity to Databricks
4. Review application logs for error details

## Cost Optimization

### Endpoint Costs

- Enable **"Scale to zero"** to reduce costs when not in use
- Choose appropriate compute size:
  - **Small**: Development/testing
  - **Medium**: Production with moderate load
  - **Large**: High-volume production

### Request Optimization

- Batch multiple products in a single request
- Cache results when appropriate
- Consider scheduled batch processing for large catalogs

## Future Enhancements

Potential improvements:
- [ ] Multi-echelon inventory optimization
- [ ] Demand forecasting integration
- [ ] What-if scenario analysis
- [ ] Supplier lead time integration
- [ ] Seasonal demand adjustment
- [ ] Real-time inventory tracking
- [ ] Automated reorder triggers
- [ ] Integration with ERP systems

## References

- [Economic Order Quantity (EOQ) Model](https://en.wikipedia.org/wiki/Economic_order_quantity)
- [Databricks MLflow Model Serving](https://docs.databricks.com/machine-learning/model-serving/index.html)
- [Safety Stock Calculations](https://en.wikipedia.org/wiki/Safety_stock)

## Support

For issues or questions:
1. Check this documentation
2. Review application logs
3. Open an issue on GitHub
4. Contact your Databricks support team
