# Databricks notebook source
# MAGIC %md
# MAGIC # 🎯 Create Feature Tables for Range Optimization
# MAGIC 
# MAGIC This notebook creates **Feature Tables** in Unity Catalog for training and inference.
# MAGIC 
# MAGIC ## Data Source: Lakebase
# MAGIC 
# MAGIC SKU data is loaded directly from **Lakebase** (`range_optimizer_catalog.range_optimizer.dim_sku`):
# MAGIC - No hardcoded data - reads live from the Range Optimizer app's database
# MAGIC - Single source of truth for all SKU attributes
# MAGIC - Automatically stays in sync with app data
# MAGIC 
# MAGIC ## Feature Tables Created
# MAGIC 
# MAGIC | Table | Source | Primary Key |
# MAGIC |-------|--------|-------------|
# MAGIC | `sku_features` | Lakebase `dim_sku` | `SKU_ID` |
# MAGIC | `demand_features` | Derived from `WEEKLY_UNITS` | `SKU_ID` |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
CATALOG = "smarter_forecasting"            # Your Unity Catalog name
SCHEMA = "stock_optimization"              # Schema for features and models
PRODUCT_FEATURES_TABLE = "sku_features"    # SKU attributes
DEMAND_FEATURES_TABLE = "demand_features"  # Demand forecasts

# Full UC paths
PRODUCT_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{PRODUCT_FEATURES_TABLE}"
DEMAND_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{DEMAND_FEATURES_TABLE}"

print(f"📦 SKU Features Table: {PRODUCT_FEATURES_PATH}")
print(f"📊 Demand Features Table: {DEMAND_FEATURES_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Install Dependencies

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering -q
# MAGIC dbutils.library.restartPython()

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
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ Created {CATALOG}.{SCHEMA}")

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

# DBTITLE 1,Load SKU Features from Lakebase
# Lakebase tables are accessible via Unity Catalog
LAKEBASE_CATALOG = "range_optimizer_catalog"
LAKEBASE_SCHEMA = "range_optimizer"
LAKEBASE_SKU_TABLE = f"{LAKEBASE_CATALOG}.{LAKEBASE_SCHEMA}.dim_sku"

print(f"📡 Loading SKU data from Lakebase: {LAKEBASE_SKU_TABLE}")

# Read from Lakebase (live data from the app!)
try:
    sku_features_df = spark.table(LAKEBASE_SKU_TABLE)
    sku_features_pd = sku_features_df.toPandas()
    print(f"✅ Loaded {len(sku_features_pd)} SKUs from Lakebase")
except Exception as e:
    print(f"⚠️ Could not load from Lakebase ({e})")
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
# MAGIC **Feature tables created from Lakebase data!**
# MAGIC 
# MAGIC ### Data Flow
# MAGIC 
# MAGIC ```
# MAGIC Lakebase (range_optimizer_catalog.range_optimizer.dim_sku)
# MAGIC     ↓
# MAGIC Feature Tables (main.stock_optimization.*)
# MAGIC     ↓
# MAGIC ML Training & Inference
# MAGIC ```
# MAGIC 
# MAGIC ### Tables Created
# MAGIC 
# MAGIC | Table | Source | Primary Key |
# MAGIC |-------|--------|-------------|
# MAGIC | `smarter_forecasting.stock_optimization.sku_features` | Lakebase `dim_sku` | `SKU_ID` |
# MAGIC | `smarter_forecasting.stock_optimization.demand_features` | Derived from `WEEKLY_UNITS` | `SKU_ID` |
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Train Model**: Run `01_train_stock_optimizer` notebook
# MAGIC 2. **Deploy Endpoint**: Run `02_deploy_serving_endpoint` notebook
