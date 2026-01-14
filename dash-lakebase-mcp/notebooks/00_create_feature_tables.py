# Databricks notebook source
# MAGIC %md
# MAGIC # 🎯 Create Feature Tables for Range Optimization
# MAGIC 
# MAGIC This notebook creates **Feature Tables** in Unity Catalog for training and inference.
# MAGIC 
# MAGIC ## Data Source: Delta Staging Table
# MAGIC 
# MAGIC SKU data is loaded from a **Delta staging table** (`{catalog}.{schema}.dim_sku_staging`):
# MAGIC - Replicated from Lakebase via SQL Warehouse (run `00a_replicate_lakebase_to_delta.sql` first)
# MAGIC - Lakebase only supports serverless SQL (DBSQL), not compute clusters
# MAGIC - The staging table is refreshed via the `replicate_lakebase` job
# MAGIC 
# MAGIC ## Feature Tables Created
# MAGIC 
# MAGIC | Table | Source | Primary Key |
# MAGIC |-------|--------|-------------|
# MAGIC | `sku_features` | Delta `dim_sku_staging` | `SKU_ID` |
# MAGIC | `demand_features` | Derived from `WEEKLY_UNITS` | `SKU_ID` |
from databricks.sdk.runtime import spark, dbutils, display

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Install Dependencies
# MAGIC 
# MAGIC **Note:** This must run BEFORE any variable initialization to avoid losing state after `restartPython()`.

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering -q

# COMMAND ----------

# MAGIC %md
# MAGIC Restart Python to pick up installed packages:

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
# Define widgets for job parameters (works when running interactively or as a job)
dbutils.widgets.text("catalog", "smarter_forecasting", "Catalog Name")
dbutils.widgets.text("schema", "stock_optimization", "Schema Name")
dbutils.widgets.text("catalog_storage_location", 
                     "abfss://iceberg@stdavidokeeffeinterop02.dfs.core.windows.net/root/catalogs/smarter_forecasting",
                     "Catalog Storage Location")

# Get parameter values
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
CATALOG_STORAGE_LOCATION = dbutils.widgets.get("catalog_storage_location")

# Feature table names
PRODUCT_FEATURES_TABLE = "sku_features"    # SKU attributes
DEMAND_FEATURES_TABLE = "demand_features"  # Demand forecasts

# Full UC paths
PRODUCT_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{PRODUCT_FEATURES_TABLE}"
DEMAND_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{DEMAND_FEATURES_TABLE}"

print(f"📦 SKU Features Table: {PRODUCT_FEATURES_PATH}")
print(f"📊 Demand Features Table: {DEMAND_FEATURES_PATH}")
print(f"📁 Catalog Storage: {CATALOG_STORAGE_LOCATION}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 Setup

# COMMAND ----------

# DBTITLE 1,Import Libraries
import pandas as pd
import numpy as np
from pyspark.sql import DataFrame
from pyspark.sql.types import *
from databricks.feature_engineering import FeatureEngineeringClient
from datetime import datetime, timedelta

# Initialize Feature Engineering Client
fe = FeatureEngineeringClient()
print("✅ Feature Engineering Client initialized")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗄️ Create Unity Catalog Schema

# COMMAND ----------

# DBTITLE 1,Setup Catalog & Schema
# Create catalog with managed location (required when metastore has no root storage credential)
# This ensures data has a place to live in ADLS Gen2
try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} MANAGED LOCATION '{CATALOG_STORAGE_LOCATION}'")
    print(f"✅ Created catalog {CATALOG} with managed location")
except Exception as e:
    if "already exists" in str(e).lower() or "CATALOG_ALREADY_EXISTS" in str(e):
        print(f"ℹ️ Catalog {CATALOG} already exists, continuing...")
    else:
        # Try without managed location in case catalog already exists with different config
        print(f"⚠️ Could not create with managed location ({e}), trying without...")
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        print(f"✅ Created catalog {CATALOG}")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ Created schema {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Feature Table 1: SKU Features
# MAGIC 
# MAGIC This table contains **static SKU attributes** aligned with the MCP app schema:
# MAGIC - SKU identifiers (`SKU_ID`, `SKU_NAME`)
# MAGIC - Cost and pricing (`UNIT_COST`, `UNIT_PRICE`, `GROSS_MARGIN_PCT`)
# MAGIC - Category hierarchy (`CATEGORY`, `SEGMENT`, `BRAND`)
# MAGIC - Physical attributes (`PACK_SIZE`, `PACK_WIDTH_MM`)
# MAGIC - Flags (`IS_PRIVATE_LABEL`, `IS_MUST_STOCK`, `STATUS`)

# COMMAND ----------

# DBTITLE 1,Load SKU Features from Delta Staging Table
# Data is replicated from Lakebase to Delta via SQL Warehouse (see 00a_replicate_lakebase_to_delta.sql)
# Lakebase ONLY supports serverless SQL (DBSQL), not compute clusters
STAGING_TABLE = f"{CATALOG}.{SCHEMA}.dim_sku_staging"

print(f"📡 Loading SKU data from Delta staging table: {STAGING_TABLE}")

# Read from Delta staging table (replicated from Lakebase via DBSQL)
try:
    sku_features_df = spark.table(STAGING_TABLE)
    sku_features_pd = sku_features_df.toPandas()
    print(f"✅ Loaded {len(sku_features_pd)} SKUs from Delta staging table")
except Exception as e:
    print(f"⚠️ Could not load from staging table ({e})")
    print("   ⚠️  Make sure to run '00a - Replicate Lakebase to Delta' job first!")
    print("   Falling back to sample data...")
    # Minimal fallback - just a few products for testing
    sku_features_pd = pd.DataFrame([
        {"SKU_ID": "SKU3001", "SKU_NAME": "Stone & Wood Pacific Ale 6pk", "BRAND": "Stone & Wood", "CATEGORY": "Beer & Seltzer", "SEGMENT": "Craft Beer", "PACK_SIZE": "6x330ml", "PACK_WIDTH_MM": 180, "UNIT_PRICE": 24.00, "UNIT_COST": 14.40, "GROSS_MARGIN_PCT": 40, "WEEKLY_UNITS": 85, "CURRENT_FACINGS": 3, "IS_PRIVATE_LABEL": False, "IS_MUST_STOCK": True, "STATUS": "active"},
        {"SKU_ID": "SKU4001", "SKU_NAME": "Sriracha Original 455ml", "BRAND": "Sriracha", "CATEGORY": "Hot Sauce", "SEGMENT": "Asian Style", "PACK_SIZE": "455ml", "PACK_WIDTH_MM": 80, "UNIT_PRICE": 6.50, "UNIT_COST": 2.93, "GROSS_MARGIN_PCT": 55, "WEEKLY_UNITS": 145, "CURRENT_FACINGS": 4, "IS_PRIVATE_LABEL": False, "IS_MUST_STOCK": True, "STATUS": "active"},
        {"SKU_ID": "SKU5001", "SKU_NAME": "Ben & Jerry's Cookie Dough 458ml", "BRAND": "Ben & Jerry's", "CATEGORY": "Ice Cream", "SEGMENT": "Premium Pints", "PACK_SIZE": "458ml", "PACK_WIDTH_MM": 110, "UNIT_PRICE": 13.50, "UNIT_COST": 6.75, "GROSS_MARGIN_PCT": 50, "WEEKLY_UNITS": 90, "CURRENT_FACINGS": 3, "IS_PRIVATE_LABEL": False, "IS_MUST_STOCK": True, "STATUS": "active"},
    ])

# Add timestamp if not present
if 'CREATED_AT' not in sku_features_pd.columns:
    sku_features_pd['CREATED_AT'] = datetime.now().isoformat()

print(f"📦 SKU Features ready: {len(sku_features_pd)} products")
display(sku_features_pd)

# COMMAND ----------

# DBTITLE 1,Create SKU Features Table
# Convert to Spark DataFrame
sku_features_df = spark.createDataFrame(sku_features_pd)

# Drop existing table if it exists
spark.sql(f"DROP TABLE IF EXISTS {PRODUCT_FEATURES_PATH}")

# Create the feature table
# Note: SKU_ID is the primary key for lookups
fe.create_table(
    name=PRODUCT_FEATURES_PATH,
    primary_keys=["SKU_ID"],
    df=sku_features_df,
    description="SKU features for range optimization including costs, categories, and shelf space allocation"
)

print(f"✅ Created feature table: {PRODUCT_FEATURES_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Feature Table 2: Demand Features
# MAGIC 
# MAGIC This table contains **time-varying demand metrics** for each SKU:
# MAGIC - `WEEKLY_UNITS`: Average weekly demand (aligns with sample_data)
# MAGIC - `DEMAND_STD`: Standard deviation of weekly demand
# MAGIC - `FORECAST_4W`: 4-week demand forecast
# MAGIC - `LAST_UPDATED`: Timestamp for tracking freshness

# COMMAND ----------

# DBTITLE 1,Create Demand Features from Lakebase Data
def create_demand_features(sku_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create demand features using WEEKLY_UNITS from Lakebase.
    
    The Lakebase dim_sku table already has WEEKLY_UNITS - we use that as the base
    and derive forecast metrics from it.
    """
    np.random.seed(42)
    
    # Category-based demand variation multipliers
    category_variance = {
        'Beer & Seltzer': 0.25,   # Moderate variance
        'Hot Sauce': 0.20,        # Lower variance  
        'Ice Cream': 0.35,        # Higher variance (seasonal)
    }
    
    demand_data = []
    for _, row in sku_df.iterrows():
        # Use WEEKLY_UNITS from Lakebase (already in the data!)
        weekly_units = row.get('WEEKLY_UNITS', 50)
        if pd.isna(weekly_units):
            weekly_units = 50
        weekly_units = float(weekly_units)
        
        # Calculate standard deviation based on category
        category = row.get('CATEGORY', 'Unknown')
        variance_mult = category_variance.get(category, 0.25)
        demand_std = weekly_units * variance_mult
        
        # 4-week forecast
        forecast_4w = weekly_units * 4
        
        demand_data.append({
            'SKU_ID': row['SKU_ID'],
            'WEEKLY_UNITS': round(weekly_units, 2),
            'DEMAND_STD': round(demand_std, 2),
            'FORECAST_4W': round(forecast_4w, 2),
            'FORECAST_DATE': datetime.now().date().isoformat(),
            'LAST_UPDATED': datetime.now().isoformat()
        })
    
    return pd.DataFrame(demand_data)

# Create demand features from Lakebase data
demand_features_pd = create_demand_features(sku_features_pd)
print(f"📊 Created demand forecasts for {len(demand_features_pd)} SKUs (from Lakebase WEEKLY_UNITS)")
display(demand_features_pd)

# COMMAND ----------

# DBTITLE 1,Create Demand Features Table
# Convert to Spark DataFrame
demand_features_df = spark.createDataFrame(demand_features_pd)

# Drop existing table if it exists
spark.sql(f"DROP TABLE IF EXISTS {DEMAND_FEATURES_PATH}")

# Create the feature table
fe.create_table(
    name=DEMAND_FEATURES_PATH,
    primary_keys=["SKU_ID"],
    df=demand_features_df,
    description="Demand forecast features for range optimization including weekly units, volatility, and forecasts"
)

print(f"✅ Created feature table: {DEMAND_FEATURES_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Verify Feature Tables

# COMMAND ----------

# DBTITLE 1,Query SKU Features
print("📦 SKU Features:")
display(spark.table(PRODUCT_FEATURES_PATH))

# COMMAND ----------

# DBTITLE 1,Query Demand Features
print("📊 Demand Features:")
display(spark.table(DEMAND_FEATURES_PATH))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Feature Statistics

# COMMAND ----------

# DBTITLE 1,Summary Statistics
print("="*60)
print("📈 FEATURE TABLE STATISTICS")
print("="*60)

# SKU features
sku_count = spark.table(PRODUCT_FEATURES_PATH).count()
avg_cost = spark.table(PRODUCT_FEATURES_PATH).selectExpr("avg(UNIT_COST) as avg_cost").first()['avg_cost']
avg_price = spark.table(PRODUCT_FEATURES_PATH).selectExpr("avg(UNIT_PRICE) as avg_price").first()['avg_price']

print(f"\n📦 SKU Features ({PRODUCT_FEATURES_PATH}):")
print(f"   Total SKUs: {sku_count}")
print(f"   Average Unit Cost: ${avg_cost:.2f}")
print(f"   Average Selling Price: ${avg_price:.2f}")
print(f"   Average Margin: {((avg_price/avg_cost - 1)*100):.1f}%")

# Demand features
demand_count = spark.table(DEMAND_FEATURES_PATH).count()
total_weekly_units = spark.table(DEMAND_FEATURES_PATH).selectExpr("sum(WEEKLY_UNITS) as total").first()['total']
avg_demand_std = spark.table(DEMAND_FEATURES_PATH).selectExpr("avg(DEMAND_STD) as avg_std").first()['avg_std']

print(f"\n📊 Demand Features ({DEMAND_FEATURES_PATH}):")
print(f"   Total SKUs: {demand_count}")
print(f"   Total Weekly Units: {total_weekly_units:.0f}")
print(f"   Average Demand Volatility (σ): {avg_demand_std:.2f}")

# By category
print(f"\n📁 Demand by Category:")
category_stats = spark.sql(f"""
    SELECT 
        p.CATEGORY,
        COUNT(*) as sku_count,
        SUM(d.WEEKLY_UNITS) as total_weekly_units,
        AVG(d.DEMAND_STD) as avg_volatility
    FROM {PRODUCT_FEATURES_PATH} p
    JOIN {DEMAND_FEATURES_PATH} d ON p.SKU_ID = d.SKU_ID
    GROUP BY p.CATEGORY
    ORDER BY total_weekly_units DESC
""").collect()

for row in category_stats:
    print(f"   • {row['CATEGORY']}:")
    print(f"      SKUs: {row['sku_count']}")
    print(f"      Weekly Units: {row['total_weekly_units']:.0f}")
    print(f"      Avg Volatility: {row['avg_volatility']:.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Complete!
# MAGIC 
# MAGIC **Feature tables created from Delta staging data!**
# MAGIC 
# MAGIC ### Data Flow
# MAGIC 
# MAGIC ```
# MAGIC Lakebase (range_optimizer_catalog.range_optimizer.dim_sku)
# MAGIC     ↓  (via SQL Warehouse - DBSQL only)
# MAGIC Delta Staging ({catalog}.{schema}.dim_sku_staging)
# MAGIC     ↓  (via Spark compute)
# MAGIC Feature Tables ({catalog}.{schema}.sku_features, demand_features)
# MAGIC     ↓
# MAGIC ML Training & Inference
# MAGIC ```
# MAGIC 
# MAGIC ### Tables Created
# MAGIC 
# MAGIC | Table | Source | Primary Key |
# MAGIC |-------|--------|-------------|
# MAGIC | `{catalog}.{schema}.sku_features` | Delta `dim_sku_staging` | `SKU_ID` |
# MAGIC | `{catalog}.{schema}.demand_features` | Derived from `WEEKLY_UNITS` | `SKU_ID` |
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Train Model**: Run `01_train_stock_optimizer` notebook
# MAGIC 2. **Deploy Endpoint**: Run `02_deploy_serving_endpoint` notebook
# MAGIC 
# MAGIC ### Note on Lakebase
# MAGIC 
# MAGIC Lakebase can **only** be queried via serverless SQL (DBSQL), not Spark compute.
# MAGIC The `00a_replicate_lakebase_to_delta.sql` job handles the CTAS to Delta.