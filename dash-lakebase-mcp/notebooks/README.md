# Range Optimizer: Delta Lake Backend Setup

This directory contains notebooks for setting up the complete Delta Lake backend in Unity Catalog to support the Range Optimizer ML model.

## 📋 Overview

The Range Optimizer uses a **hybrid architecture**:

- **Lakebase (PostgreSQL)**: Operational data store for real-time app operations
- **Unity Catalog (Delta Lake)**: Analytical data warehouse for ML training and optimization

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Data Architecture                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐         ┌──────────────────┐         ┌───────────────┐
│   MCP App       │────────▶│    Lakebase      │────────▶│  Unity Catalog│
│  (FastAPI)      │         │  (PostgreSQL)    │         │  (Delta Lake) │
│                 │         │                  │         │               │
│ • User edits    │         │ • Transactional  │         │ • Analytics   │
│ • AI assistant  │         │ • Real-time      │         │ • ML training │
│ • Optimization  │         │ • Single schema  │         │ • Star schema │
└─────────────────┘         └──────────────────┘         └───────────────┘
                                     │                            │
                                     │                            │
                                     ▼                            ▼
                            ┌──────────────────┐         ┌───────────────┐
                            │  UI App (Dash)   │         │ ML Pipeline   │
                            │                  │         │               │
                            │ • Data grids     │         │ • Feature eng │
                            │ • Dashboards     │         │ • Model train │
                            │ • Visualizations │         │ • Serving     │
                            └──────────────────┘         └───────────────┘
```

## 📚 Notebooks

### 1. `00_setup_delta_backend.py`

**Purpose:** Create complete star schema in Unity Catalog

**Creates:**
- 5 dimensional tables (`dim_sku`, `dim_store`, `dim_category`, `dim_brand`, `dim_time`)
- 3 fact tables (`fact_sales_weekly`, `fact_planogram_current`, `fact_shelf_inventory`)
- 3 configuration tables (`cfg_range_constraints`, `cfg_merchandising_rules`, `cfg_sku_cost_margin`)
- 2 analytics tables (`agg_sku_performance_weekly`, `ml_demand_forecast`)
- 3 optimization tables (`opt_recommended_planogram`, `opt_optimization_run_summary`, `opt_constraint_violations`)

**Parameters:**
- `catalog`: Target Unity Catalog name (default: `range_optimizer_catalog`)
- `schema`: Target schema name (default: `range_optimizer`)
- `catalog_storage_location`: ADLS Gen2 path for catalog storage
- `load_sample_data`: Whether to load sample data (default: `true`)

**Sample Data:**
- 15 SKUs across 3 categories (Beer & Seltzer, Hot Sauce, Ice Cream)
- 2 stores in Melbourne
- 52 weeks of synthetic sales data
- Demand forecasts for all SKUs

**Run:**
```bash
databricks jobs run-now --job-name "Setup Delta Backend"
```

Or interactively in Databricks notebook.

---

### 2. `00a_replicate_lakebase_to_delta.sql`

**Purpose:** Replicate operational data from Lakebase to Delta staging tables

**Why needed:**
- Lakebase can ONLY be accessed via SQL Warehouse (DBSQL), not Spark compute
- ML pipelines require Spark compute for feature engineering
- Solution: CTAS (Create Table As Select) to replicate to Delta

**Replicates:**
- `dim_sku` → `dim_sku_staging`
- `dim_category` → `dim_category_staging`
- `dim_brand` → `dim_brand_staging`
- `fact_sales_weekly` → `fact_sales_staging` (last 52 weeks)
- `ml_demand_forecast` → `ml_demand_forecast_staging`
- `opt_recommended_planogram` → `opt_planogram_staging` (last 30 days)

**Schedule:** Daily at 2:00 AM via SQL Warehouse job

**Run:**
```sql
-- Set parameters in notebook
SET catalog = range_optimizer_catalog;
SET target_catalog = smarter_forecasting;
SET schema = range_optimizer;
SET target_schema = stock_optimization;

-- Run all cells
```

---

### 3. `00_create_feature_tables.py`

**Purpose:** Create Feature Store tables for ML model training

**Creates:**
- `sku_features`: Static product attributes (cost, price, category, shelf space)
- `demand_features`: Demand forecasts and volatility metrics

**Data source:** Delta staging tables (replicated from Lakebase)

**Features:**
- Uses Databricks Feature Engineering Client
- Automatic feature lookup during inference
- Feature-to-model lineage tracking

**Run:**
```python
uv run databricks jobs run-now --job-name "Create Feature Tables"
```

---

### 4. `01_train_stock_optimizer.py`

**Purpose:** Train EOQ-based stock optimization model using Feature Store

**Algorithm:** Economic Order Quantity (EOQ) with safety stock optimization

**Inputs:**
- SKU features (from Feature Store)
- Demand features (from Feature Store)
- Business constraints (from config tables)

**Outputs:**
- Optimal order quantity
- Safety stock levels
- Reorder points
- Expected costs and profitability

**Model registration:** Logs to MLflow with Feature Store metadata

**Run:**
```python
uv run databricks jobs run-now --job-name "Train Stock Optimizer"
```

---

### 5. `02_deploy_serving_endpoint.py`

**Purpose:** Deploy trained model to Databricks Model Serving

**Creates:**
- Real-time serving endpoint
- Auto-scaling configuration
- Feature lookup integration

**Endpoint:** `stock-optimizer-serving`

**Run:**
```python
uv run databricks jobs run-now --job-name "Deploy Serving Endpoint"
```

---

## 🔄 Data Flow

### Complete Pipeline

```
1. User edits data in UI App (Dash)
           ↓
2. Changes written to Lakebase (PostgreSQL)
           ↓
3. Daily replication job copies to Delta staging tables
           ↓
4. Feature engineering creates feature tables
           ↓
5. Model training uses Feature Store
           ↓
6. Model deployed to serving endpoint
           ↓
7. MCP App calls optimization endpoint
           ↓
8. Results written back to Lakebase
           ↓
9. UI App displays recommendations
```

### Daily Schedule

| Time | Job | Purpose |
|------|-----|---------|
| 02:00 | Lakebase → Delta replication | Sync operational data |
| 03:00 | Feature engineering | Update feature tables |
| 04:00 | Model training (weekly) | Retrain optimization model |
| 05:00 | Model deployment (weekly) | Update serving endpoint |

---

## 🚀 Getting Started

### Prerequisites

1. **Unity Catalog setup:**
   ```bash
   # Verify Unity Catalog access
   uv run python scripts/verify_uc_catalog.py
   ```

2. **Lakebase instance running:**
   ```bash
   # Check Lakebase connection
   databricks database list-database-instances
   ```

3. **SQL Warehouse available:**
   ```bash
   # List SQL Warehouses
   databricks sql-warehouses list
   ```

### Initial Setup

1. **Create Unity Catalog schema:**
   ```bash
   # Run setup notebook
   databricks jobs create --json @jobs/setup_delta_backend.json
   databricks jobs run-now --job-name "Setup Delta Backend"
   ```

2. **Verify tables created:**
   ```sql
   USE CATALOG range_optimizer_catalog;
   USE SCHEMA range_optimizer;
   SHOW TABLES;
   ```

3. **Load sample data** (if empty):
   ```bash
   # Run with load_sample_data=true
   databricks jobs run-now --job-name "Setup Delta Backend" \
     --notebook-params '{"load_sample_data": "true"}'
   ```

4. **Set up replication job:**
   ```bash
   # Create SQL Warehouse job for replication
   databricks jobs create --json @jobs/replicate_lakebase.json
   ```

5. **Create feature tables:**
   ```bash
   databricks jobs run-now --job-name "Create Feature Tables"
   ```

6. **Train initial model:**
   ```bash
   databricks jobs run-now --job-name "Train Stock Optimizer"
   ```

7. **Deploy serving endpoint:**
   ```bash
   databricks jobs run-now --job-name "Deploy Serving Endpoint"
   ```

---

## 📊 Schema Reference

### Dimensional Tables

#### `dim_sku` - Product Master
- **Grain:** One row per SKU
- **Key columns:** `sku_id`, `sku_name`, `brand_id`, `category_id`
- **Metrics:** `unit_price`, `unit_cost`, `gross_margin_pct`, `weekly_units`
- **Attributes:** `pack_width_mm`, `is_must_stock`, `sku_status`

#### `dim_store` - Store Master
- **Grain:** One row per store
- **Key columns:** `store_id`, `store_code`, `planogram_cluster_id`
- **Attributes:** `store_format`, `region_name`, `city`, `affluence_segment`

#### `dim_category` - Category Hierarchy
- **Grain:** One row per category
- **Hierarchy:** `parent_category_id` for multi-level hierarchy
- **Attributes:** `category_role`, `space_priority`, `is_chill_category`

#### `dim_brand` - Brand Master
- **Grain:** One row per brand
- **Key columns:** `brand_id`, `brand_name`, `manufacturer_id`

#### `dim_time` - Time Dimension
- **Grain:** One row per week
- **Key columns:** `time_id`, `date_key`, `week_start_date`
- **Attributes:** `is_holiday`, `holiday_name`

---

### Fact Tables

#### `fact_sales_weekly` - Historical Sales
- **Grain:** Store × SKU × Week
- **Partitioning:** By `week_start_date`
- **Metrics:** `units_sold`, `net_sales_value`, `availability_rate`
- **Flags:** `promo_flag`, `on_display_flag`

#### `fact_planogram_current` - Current Layout
- **Grain:** Store × Category × SKU
- **Metrics:** `total_facings`, `effective_width_mm`, `is_eye_level`
- **Position:** `shelf_id`, `shelf_level`, `position_order`

#### `fact_shelf_inventory` - Shelf Constraints
- **Grain:** Store × Category × Shelf
- **Constraints:** `total_width_mm`, `max_weight_kg`
- **Utilization:** `current_utilized_width_mm`, `current_available_width_mm`

---

### Configuration Tables

#### `cfg_range_constraints` - Range Rules
- **Scope:** Store or Cluster × Category
- **Rules:** `min_range_size`, `max_range_size`, `min_facings_per_sku`
- **Share limits:** `min_private_label_share`, `max_any_brand_share`
- **Forced lists:** `forced_include_skus`, `forced_exclude_skus`

#### `cfg_merchandising_rules` - Advanced Rules
- **Generic structure:** `rule_type`, `parameter_1`, `parameter_1_value`
- **Rule types:** `brand_blocking`, `adjacency`, `min_facings`, `segment_share`
- **Priority:** Lower number = higher priority

#### `cfg_sku_cost_margin` - Cost & Margin (SCD Type 2)
- **Versioning:** `valid_from_date`, `valid_to_date`
- **Costs:** `cost_price`, `regular_retail_price`, `suggested_promo_price`
- **Margins:** `gross_margin_pct`, `contribution_margin`

---

### Analytics Tables

#### `agg_sku_performance_weekly` - SKU Metrics
- **Grain:** SKU × Week
- **Aggregates:** `total_units_sold`, `total_sales_value`, `avg_price`
- **Performance:** `promo_lift_pct`, `stores_in_range_count`, `segment_rank`

#### `ml_demand_forecast` - Demand Forecasts
- **Grain:** Store/Cluster × SKU × Forecast period
- **Forecasts:** `baseline_demand_units`, `demand_with_promo_units`, `demand_with_space_units`
- **Accuracy:** `forecast_accuracy_mape`

---

### Optimization Tables

#### `opt_recommended_planogram` - Optimizer Output
- **Grain:** Store/Cluster × Category × SKU × Run
- **Partitioning:** By `optimization_run_date`
- **Recommendations:** `is_ranged_recommended`, `recommended_facings`
- **Expected results:** `expected_units_weekly`, `expected_margin_weekly`
- **Change tracking:** `change_from_current`, `facings_change`, `execution_difficulty`

#### `opt_optimization_run_summary` - Run Metadata
- **Grain:** One row per optimization run
- **Scope:** `stores_included`, `categories_included`, `clusters_optimized`
- **Results:** `objective_value`, `total_expected_revenue`, `total_expected_margin`
- **Solver:** `solver_name`, `solver_status`, `solver_time_seconds`

#### `opt_constraint_violations` - Violations
- **Grain:** Violation per run
- **Details:** `constraint_type`, `violation_magnitude`, `severity`

---

## 🔧 Maintenance

### Monitoring

```sql
-- Check replication freshness
SELECT table_name, MAX(replicated_at) AS last_replicated
FROM (
  SELECT 'dim_sku_staging' AS table_name, MAX(replicated_at) AS replicated_at
  FROM smarter_forecasting.stock_optimization.dim_sku_staging
  UNION ALL
  SELECT 'fact_sales_staging', MAX(replicated_at)
  FROM smarter_forecasting.stock_optimization.fact_sales_staging
);

-- Check feature table stats
DESCRIBE FEATURE smarter_forecasting.stock_optimization.sku_features;
DESCRIBE FEATURE smarter_forecasting.stock_optimization.demand_features;
```

### Troubleshooting

**Issue:** Lakebase tables not found
```bash
# Verify Lakebase catalog registration
uv run python scripts/verify_uc_catalog.py

# Re-register if needed
uv run python scripts/register_database_to_uc.py
```

**Issue:** Feature table lookup fails
```python
# Check feature table registration
from databricks.feature_engineering import FeatureEngineeringClient
fe = FeatureEngineeringClient()
fe.get_table(name="smarter_forecasting.stock_optimization.sku_features")
```

**Issue:** Model serving endpoint down
```bash
# Check endpoint status
databricks serving-endpoints get --name stock-optimizer-serving

# Restart if needed
databricks serving-endpoints update --name stock-optimizer-serving --config @serving_config.json
```

---

## 📚 Additional Resources

- [Range Optimizer Schema Reference](../ui_app/range_optimizer_schema.md)
- [MCP App Documentation](../mcp_app/README.md)
- [UI App Documentation](../ui_app/README.md)
- [Databricks Feature Store Docs](https://docs.databricks.com/machine-learning/feature-store/index.html)
- [Unity Catalog Docs](https://docs.databricks.com/data-governance/unity-catalog/index.html)

---

## 🎯 Next Steps

1. **Schedule jobs:** Set up daily replication and weekly retraining
2. **Monitor performance:** Track model accuracy and optimization quality
3. **Extend schema:** Add competitor pricing, promotional calendar, etc.
4. **Optimize queries:** Add materialized views for common analytics
5. **Implement CDC:** Use Change Data Capture for real-time sync
