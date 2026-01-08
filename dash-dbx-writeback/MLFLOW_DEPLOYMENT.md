# MLflow Model Serving Deployment - Complete

## ✅ What We Accomplished

### 1. **Model Registration**
- **Model Name**: `stock-optimization-model`
- **Registry**: Databricks Workspace Model Registry
- **Version**: 1
- **Run ID**: `1c8053a79b28454c86931e9bcc4534dd`
- **Experiment**: `/Users/david.okeeffe@databricks.com/stock-optimization`

**View in Databricks**:
- Experiments: https://adb-7405614596482958.18.azuredatabricks.net/ml/experiments/2885954621614515
- Run: https://adb-7405614596482958.18.azuredatabricks.net/ml/experiments/2885954621614515/runs/1c8053a79b28454c86931e9bcc4534dd

### 2. **Serving Endpoint Creation**
- **Endpoint Name**: `stock-optimization-model`
- **Status**: `DEPLOYMENT_CREATING` → Will become `READY` in 5-10 minutes
- **Workload Size**: Small
- **Scale to Zero**: Enabled (cost optimization)
- **Endpoint ID**: `729c80666c2f4550a23b93fe455cdffc`

**Check Status**:
```bash
databricks serving-endpoints get stock-optimization-model
```

### 3. **Application Integration**
The Coles Inventory Intelligence app already has **hybrid optimization** built in:

```python
class HybridStockOptimizer:
    def optimize(self, forecast_data):
        try:
            # Try MLflow Model Serving endpoint FIRST
            client = MLflowModelClient("stock-optimization-model")
            result_df = client.predict(forecast_data)
            return result_df, "mlflow"  # ✅ Will use endpoint once ready
        except Exception:
            # Fall back to local EOQ model
            result_df = FallbackOptimizer.optimize(forecast_data)
            return result_df, "fallback"  # Currently using this
```

**Current Behavior**:
- ⏳ **While endpoint is deploying**: Uses local EOQ fallback
- ✅ **Once endpoint is ready**: Automatically switches to MLflow endpoint

No code changes needed - it's already wired up!

### 4. **Model Details**

#### **Input Schema**:
```python
{
    'SELL_ID': str,
    'PRODUCT_NAME': str,
    'AVG_DAILY_DEMAND': float,
    'DEMAND_STD': float,
    'TOTAL_FORECAST_30D': float,
    'UNIT_COST': float,
    'SELLING_PRICE': float,
}
```

#### **Output Schema**:
```python
{
    'SELL_ID': str,
    'PRODUCT_NAME': str,
    'AVG_DAILY_DEMAND': float,
    'OPTIMAL_ORDER_QTY': float,       # EOQ calculation
    'SAFETY_STOCK': float,             # Buffer inventory
    'REORDER_POINT': float,            # When to reorder
    'MAX_STOCK_LEVEL': float,          # Maximum inventory
    'TOTAL_ANNUAL_COST': float,        # Holding + Ordering costs
    'EXPECTED_ANNUAL_REVENUE': float,  # Revenue projection
    'EXPECTED_ANNUAL_PROFIT': float,   # Profit projection
    'TURNOVER_RATE': float,            # How fast inventory moves
    'SERVICE_LEVEL': float,            # Target service level (95%)
}
```

#### **Optimization Algorithm**:
- **Economic Order Quantity (EOQ)**: Balances ordering costs vs holding costs
- **Safety Stock**: Z-score (1.65) * demand std dev * √lead time
- **Reorder Point**: (avg daily demand * lead time) + safety stock
- **Max Stock**: Reorder point + EOQ
- **Financial Metrics**: Annual costs, revenue, profit projections

## 🔄 How It Works End-to-End

### Workflow:
1. **User submits forecast** in Coles app (Input page)
2. **Forecast saved** to `excel_app.forecast_submissions` table
3. **Optimization automatically triggered** via `run_stock_optimization_for_forecast()`
4. **Hybrid optimizer attempts**:
   - **Primary**: Call MLflow serving endpoint
   - **Fallback**: Use local EOQ model if endpoint unavailable
5. **Results saved** to `excel_app.stock_optimization_results` table
6. **User views results** on Stock Optimization page with charts

### Data Flow:
```
Coles Staff
    ↓ Submit Forecast (Category: Dairy, Bakery, etc.)
Dash App (Input Page)
    ↓ Save to Database
PostgreSQL (forecast_submissions)
    ↓ Trigger Optimization
Hybrid Optimizer
    ├─→ Try MLflow Endpoint (stock-optimization-model) ✅ NEW!
    └─→ Fallback: Local EOQ Model
Results
    ↓ Save Optimized Stock Levels
PostgreSQL (stock_optimization_results)
    ↓ Load & Display
Stock Optimization Page (Charts + Grid)
    ↓ View Results
Coles Staff
```

## 📊 Monitoring & Verification

### Check Endpoint Status:
```bash
# Get endpoint status
databricks serving-endpoints get stock-optimization-model

# Wait for it to become READY
databricks serving-endpoints get stock-optimization-model | grep "ready"
# Should show: "ready":"READY"
```

### Test the Endpoint:
```bash
# Create test payload
cat > test_payload.json << 'EOF'
{
  "dataframe_records": [
    {
      "SELL_ID": "TEST001",
      "PRODUCT_NAME": "Test Product",
      "AVG_DAILY_DEMAND": 100.0,
      "DEMAND_STD": 15.0,
      "TOTAL_FORECAST_30D": 3000.0,
      "UNIT_COST": 10.0,
      "SELLING_PRICE": 20.0
    }
  ]
}
EOF

# Test the endpoint
curl -X POST \
  https://adb-7405614596482958.18.azuredatabricks.net/serving-endpoints/stock-optimization-model/invocations \
  -H "Authorization: Bearer $(databricks auth token)" \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

### Verify in App:
1. Go to: https://excel-the-dash-way-7405614596482958.18.azure.databricksapps.com
2. Navigate to **Input** page
3. Select a category (e.g., "Dairy")
4. Click **"Submit Forecast Run"**
5. Check the success message:
   - If endpoint is ready: `"Stock optimization completed using mlflow method"`
   - If still deploying: `"Stock optimization completed using fallback method"`
6. Navigate to **Stock Optimization** page
7. Select your forecast ID
8. View results!

## 🎯 Benefits of MLflow Serving

### Why Use MLflow Endpoint vs Local?

| Aspect | MLflow Endpoint | Local Fallback |
|--------|----------------|----------------|
| **Scalability** | ✅ Auto-scaling | ❌ Single process |
| **Performance** | ✅ Dedicated compute | ⚠️ Shares app resources |
| **Versioning** | ✅ Model versions tracked | ❌ Code-level only |
| **Monitoring** | ✅ Built-in metrics | ❌ Manual logging |
| **Updates** | ✅ Deploy new model versions | ❌ Requires code deployment |
| **A/B Testing** | ✅ Traffic splitting | ❌ Not supported |
| **Cost** | ⚠️ Endpoint charges | ✅ No extra cost |

### Production Best Practices:
1. **Use MLflow endpoint** for production workloads
2. **Keep fallback** for development and resilience
3. **Monitor usage**: Check which method is being used
4. **Version models**: Update models without changing code
5. **Scale as needed**: Increase workload size for more traffic

## 📝 Configuration Files

### Model Registration (`deploy_model_to_mlflow.py`):
- Creates MLflow experiment
- Logs model with signature
- Registers in Workspace Model Registry
- ✅ **Already run successfully**

### Serving Endpoint (`resources/model_serving.yml`):
```yaml
resources:
  model_serving_endpoints:
    stock_optimization_endpoint:
      name: stock-optimization-model
      config:
        served_entities:
          - entity_name: stock-optimization-model
            entity_version: "1"
            workload_size: Small
            scale_to_zero_enabled: true
```

### Application Code:
- `src/dash_dbx_writeback/ml/mlflow_client.py`: Hybrid optimizer
- `src/dash_dbx_writeback/ml/stock_optimizer.py`: EOQ algorithm
- `src/dash_dbx_writeback/ml/forecast_optimizer.py`: Integration layer

## 🚀 Next Steps

1. **Wait for endpoint** to become READY (5-10 min)
   ```bash
   watch -n 30 'databricks serving-endpoints get stock-optimization-model | grep ready'
   ```

2. **Test the endpoint** once ready (see Test section above)

3. **Submit a forecast** in the Coles app and verify it uses MLflow:
   - Success message should say: `"using mlflow method"`
   - Check logs: Look for `"✓ Optimization complete using 'mlflow' method"`

4. **Monitor performance**:
   - View endpoint metrics in Databricks UI
   - Check latency and throughput
   - Monitor costs (scale-to-zero helps!)

5. **(Optional) Update model**:
   - Deploy new model version
   - Update serving endpoint to version 2
   - A/B test between versions

## 🔗 Useful Links

- **App URL**: https://excel-the-dash-way-7405614596482958.18.azure.databricksapps.com
- **MLflow Experiment**: https://adb-7405614596482958.18.azuredatabricks.net/ml/experiments/2885954621614515
- **Model Registry**: Workspace → Machine Learning → Models → `stock-optimization-model`
- **Serving Endpoints**: Workspace → Machine Learning → Serving

## ✅ Success Criteria

The deployment is successful when:
- ✅ Model registered in Workspace Model Registry
- ⏳ Serving endpoint status: `READY` (currently: `DEPLOYMENT_CREATING`)
- ✅ App has hybrid optimizer configured
- ⏳ Forecast submission uses MLflow method (will happen once endpoint is ready)

**Current Status**: 🟡 Deployment in progress
**Expected Completion**: ~5-10 minutes from now

---

**Deployed**: 2026-01-07 11:02 GMT
**By**: David O'Keeffe
**Workspace**: adb-7405614596482958.18.azuredatabricks.net
