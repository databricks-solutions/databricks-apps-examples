# Range Optimizer: Architecture Overview

## 🏗️ Current Architecture

Your Range Optimizer uses a **hybrid dual-catalog architecture** with Unity Catalog:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Range Optimizer Architecture                      │
└─────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════╗
║  range_optimizer_catalog.range_optimizer                           ║
║  (Lakebase PostgreSQL via Unity Catalog FOREIGN tables)           ║
╚═══════════════════════════════════════════════════════════════════╝
         │
         │  Unity Catalog Foreign Table Connection
         │  (Direct access to Lakebase PostgreSQL)
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Lakebase PostgreSQL Database                                       │
│  • Operational data store                                           │
│  • Real-time transactional operations                               │
│  • Single normalized schema                                         │
└─────────────────────────────────────────────────────────────────────┘
         ↕
┌─────────────────────────────────────────────────────────────────────┐
│  MCP App (FastAPI) + UI App (Dash)                                  │
│  • User edits and submissions                                       │
│  • AI assistant operations                                          │
│  • Real-time optimization                                           │
└─────────────────────────────────────────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════╗
║  smarter_forecasting.stock_optimization                            ║
║  (Unity Catalog MANAGED Delta Lake tables)                         ║
╚═══════════════════════════════════════════════════════════════════╝
         │
         │  Spark Compute Access
         │  (Feature engineering, ML training, analytics)
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Delta Lake Tables (ADLS Gen2)                                      │
│  • Star schema for analytics                                        │
│  • Feature Store tables                                             │
│  • ML model training data                                           │
└─────────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│  ML Pipeline                                                         │
│  • Feature engineering                                              │
│  • Model training (EOQ optimization)                                │
│  • Model serving endpoint                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Catalog Structure

### 1. `range_optimizer_catalog.range_optimizer`

**Type:** Unity Catalog FOREIGN tables (pointing to Lakebase PostgreSQL)

**Purpose:** Operational data store for real-time app operations

**Access:** SQL Warehouse (DBSQL) or Spark with Unity Catalog

**Tables:**

| Table | Type | Rows | Purpose |
|-------|------|------|---------|
| `dim_sku` | FOREIGN (PostgreSQL) | ~15 | Product master |
| `demand_forecast` | FOREIGN (PostgreSQL) | ~15 | Demand forecasts |
| `opt_recommended_planogram` | FOREIGN (PostgreSQL) | Variable | Optimization results |
| `optimization_runs` | FOREIGN (PostgreSQL) | Variable | Run history |
| `stock_optimization_results` | FOREIGN (PostgreSQL) | Variable | Optimization outputs |

**Key Characteristics:**
- ✅ Real-time access via MCP and UI apps
- ✅ Transactional CRUD operations
- ✅ Direct PostgreSQL performance
- ✅ Accessible via Unity Catalog (no need for JDBC)
- ⚠️ Limited to SQL Warehouse for queries (Lakebase restriction)

---

### 2. `smarter_forecasting.stock_optimization`

**Type:** Unity Catalog MANAGED Delta Lake tables

**Purpose:** Analytics warehouse and ML feature store

**Access:** Spark compute clusters

**Tables:**

| Table | Type | Rows | Purpose |
|-------|------|------|---------|
| `sku_features` | MANAGED (Delta) | ~15 | **Feature Store** - Product attributes |
| `demand_features` | MANAGED (Delta) | ~15 | **Feature Store** - Demand metrics |
| `dim_sku_staging` | MANAGED (Delta) | ~15 | Staging copy of SKU master |
| `dim_store` | MANAGED (Delta) | 2 | Store master dimension |
| `dim_category` | MANAGED (Delta) | 3 | Category hierarchy |
| `dim_brand` | MANAGED (Delta) | 8 | Brand master |
| `fact_sales_weekly` | MANAGED (Delta) | ~360 | Historical sales (12 weeks) |
| `fact_planogram_current` | MANAGED (Delta) | TBD | Current shelf layout |
| `cfg_range_constraints` | MANAGED (Delta) | TBD | Business rules |

**Key Characteristics:**
- ✅ Full Spark compute access
- ✅ Feature Store integration
- ✅ Optimized for analytics (star schema)
- ✅ Time travel and ACID transactions
- ✅ Partitioned tables for performance
- ✅ ML model training ready

---

## 🔄 Data Flow

### Operational Flow (Real-time)

```
1. User edits data in UI App
   ↓
2. POST to MCP App API
   ↓
3. Write to Lakebase PostgreSQL
   ↓
4. Immediately visible in range_optimizer_catalog.range_optimizer
   ↓
5. UI App refreshes and displays updated data
```

### Analytics Flow (Batch)

```
1. Lakebase PostgreSQL (operational data)
   ↓
2. Unity Catalog FOREIGN tables (range_optimizer_catalog.range_optimizer)
   ↓
3. Periodic sync to Delta staging (smarter_forecasting.stock_optimization.dim_sku_staging)
   ↓
4. Feature engineering creates Feature Store tables
   ↓
5. ML model training uses Feature Store
   ↓
6. Model deployed to serving endpoint
   ↓
7. MCP App calls optimization endpoint
   ↓
8. Results written back to Lakebase
```

---

## 🎯 Why This Architecture?

### Problem: Lakebase Limitations

**Lakebase can ONLY be accessed via:**
- SQL Warehouse (DBSQL) - serverless SQL
- Unity Catalog FOREIGN tables

**Lakebase CANNOT be accessed via:**
- Spark compute clusters directly
- Standard JDBC connections from notebooks

### Solution: Dual-Catalog Architecture

1. **`range_optimizer_catalog`** (Lakebase via Unity Catalog)
   - Real-time operational data
   - Direct access for MCP/UI apps
   - No replication lag
   - Transactional consistency

2. **`smarter_forecasting`** (Delta Lake)
   - Analytics and ML workloads
   - Full Spark compute access
   - Feature Store integration
   - Star schema optimization

### Benefits

✅ **Best of both worlds:**
- Real-time operations on Lakebase
- Advanced analytics on Delta Lake

✅ **No replication lag for operations:**
- MCP/UI apps read directly from Lakebase via Unity Catalog
- Instant consistency for user edits

✅ **Optimized for ML:**
- Feature Store requires Delta Lake
- Spark compute for feature engineering
- Model training on optimized star schema

✅ **Unified governance:**
- All data accessible via Unity Catalog
- Single permission model
- Lineage tracking across both catalogs

---

## 📚 Table Mapping

### Operational Tables (Lakebase)

| Lakebase Table | Unity Catalog Path | Purpose |
|----------------|-------------------|---------|
| `dim_sku` | `range_optimizer_catalog.range_optimizer.dim_sku` | Product master (operational) |
| `demand_forecast` | `range_optimizer_catalog.range_optimizer.demand_forecast` | Demand forecasts (operational) |
| `opt_recommended_planogram` | `range_optimizer_catalog.range_optimizer.opt_recommended_planogram` | Optimization results |

### Analytics Tables (Delta Lake)

| Delta Table | Unity Catalog Path | Purpose |
|-------------|-------------------|---------|
| `sku_features` | `smarter_forecasting.stock_optimization.sku_features` | Feature Store - SKU attributes |
| `demand_features` | `smarter_forecasting.stock_optimization.demand_features` | Feature Store - Demand metrics |
| `dim_sku_staging` | `smarter_forecasting.stock_optimization.dim_sku_staging` | Staging copy for ML |
| `fact_sales_weekly` | `smarter_forecasting.stock_optimization.fact_sales_weekly` | Historical sales for analytics |

---

## 🚀 Access Patterns

### MCP App (FastAPI)

```python
# Direct access to Lakebase via Unity Catalog
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Query operational data (FOREIGN tables)
result = w.statement_execution.execute_statement(
    warehouse_id="your-warehouse-id",
    statement="SELECT * FROM range_optimizer_catalog.range_optimizer.dim_sku",
    catalog="range_optimizer_catalog",
    schema="range_optimizer"
)
```

### UI App (Dash)

```python
# Same as MCP app - direct Lakebase access
# Uses SQL Warehouse for queries
```

### ML Notebooks (Spark)

```python
# Access Delta Lake tables for analytics
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# Read from Delta Lake (MANAGED tables)
sku_features = spark.table("smarter_forecasting.stock_optimization.sku_features")
demand_features = spark.table("smarter_forecasting.stock_optimization.demand_features")

# Feature Store integration
from databricks.feature_engineering import FeatureEngineeringClient
fe = FeatureEngineeringClient()

# Create training set with automatic feature lookup
training_set = fe.create_training_set(
    df=labels_df,
    feature_lookups=[
        FeatureLookup(
            table_name="smarter_forecasting.stock_optimization.sku_features",
            lookup_key="SKU_ID"
        ),
        FeatureLookup(
            table_name="smarter_forecasting.stock_optimization.demand_features",
            lookup_key="SKU_ID"
        )
    ],
    label="target"
)
```

---

## 📈 Performance Characteristics

### Lakebase (Operational)

| Metric | Value | Notes |
|--------|-------|-------|
| Query latency | <100ms | Direct PostgreSQL performance |
| Write latency | <50ms | Transactional consistency |
| Concurrent users | 100+ | SQL Warehouse auto-scaling |
| Data freshness | Real-time | No replication lag |

### Delta Lake (Analytics)

| Metric | Value | Notes |
|--------|-------|-------|
| Query latency | 1-5s | Spark startup + query execution |
| Scan performance | 1GB/s+ | Columnar format, partitioning |
| Time travel | ✅ | Access historical versions |
| ACID transactions | ✅ | Delta Lake guarantees |

---

## 🔧 Maintenance

### No Replication Needed!

Unlike traditional architectures, you **don't need** a replication job because:

1. **Operational data** is accessed directly via Unity Catalog FOREIGN tables
2. **Analytics data** is created independently via feature engineering
3. **No sync lag** between operational and analytical views

### Optional: Staging Refresh

If you want to refresh the staging tables periodically:

```sql
-- Refresh dim_sku_staging from Lakebase
CREATE OR REPLACE TABLE smarter_forecasting.stock_optimization.dim_sku_staging AS
SELECT * FROM range_optimizer_catalog.range_optimizer.dim_sku;
```

But this is **optional** - the Feature Store tables are the source of truth for ML.

---

## 🎉 Summary

Your Range Optimizer has a **production-ready hybrid architecture**:

✅ **Operational Excellence**
- Real-time access to Lakebase via Unity Catalog
- No replication lag
- Transactional consistency

✅ **Analytics Power**
- Full Spark compute access for ML
- Feature Store integration
- Star schema optimization

✅ **Unified Governance**
- Single Unity Catalog interface
- Consistent permissions
- End-to-end lineage

✅ **Best Performance**
- Direct PostgreSQL for operations (<100ms)
- Optimized Delta Lake for analytics
- Auto-scaling for both workloads

This architecture leverages the **best of both worlds** - the transactional power of PostgreSQL (Lakebase) and the analytical capabilities of Delta Lake! 🚀
