# Databricks notebook source
# MAGIC %md
# MAGIC # 🔧 Extend Delta Lake Schema for Range Optimizer
# MAGIC 
# MAGIC This notebook **extends** the existing Delta Lake schema with additional tables from the star schema design.
# MAGIC 
# MAGIC ## Current Setup
# MAGIC 
# MAGIC You already have:
# MAGIC - **`range_optimizer_catalog.range_optimizer`**: Lakebase (PostgreSQL) tables via Unity Catalog
# MAGIC - **`smarter_forecasting.stock_optimization`**: Delta Lake tables for ML/analytics
# MAGIC 
# MAGIC ## This Notebook Adds
# MAGIC 
# MAGIC Additional tables to complete the star schema:
# MAGIC - `dim_store`, `dim_category`, `dim_brand`, `dim_time` (dimensions)
# MAGIC - `fact_sales_weekly`, `fact_planogram_current`, `fact_shelf_inventory` (facts)
# MAGIC - `cfg_range_constraints`, `cfg_merchandising_rules`, `cfg_sku_cost_margin` (config)
# MAGIC - `agg_sku_performance_weekly` (analytics)
# MAGIC - `opt_optimization_run_summary`, `opt_constraint_violations` (optimization metadata)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Setup Parameters
# Use existing catalogs
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"
LOAD_SAMPLE_DATA = True

print(f"📦 Catalog: {CATALOG}")
print(f"📊 Schema: {SCHEMA}")
print(f"🔄 Load Sample Data: {LOAD_SAMPLE_DATA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 Setup

# COMMAND ----------

# DBTITLE 1,Import Libraries
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pyspark.sql.types import *
from pyspark.sql import functions as F

print("✅ Libraries imported")

# Use the schema
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Check Existing Tables

# COMMAND ----------

# DBTITLE 1,List Current Tables
existing_tables = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").toPandas()
print(f"📋 Existing tables in {CATALOG}.{SCHEMA}:")
display(existing_tables)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Create Additional Dimensional Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_store - Store Master

# COMMAND ----------

# DBTITLE 1,Create dim_store
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.dim_store (
  store_id STRING PRIMARY KEY,
  store_name STRING NOT NULL,
  store_code STRING NOT NULL,
  store_format STRING,
  store_size_sqm INT,
  region_id STRING,
  region_name STRING,
  city STRING,
  postcode STRING,
  country STRING,
  affluence_segment STRING,
  demographic_profile STRING,
  opening_date DATE,
  closing_date DATE,
  planogram_cluster_id STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Store master dimension with location and demographic attributes'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.dim_store")

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_category - Category Hierarchy

# COMMAND ----------

# DBTITLE 1,Create dim_category
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.dim_category (
  category_id STRING PRIMARY KEY,
  category_name STRING NOT NULL,
  department STRING,
  parent_category_id STRING,
  category_role STRING,
  space_priority INT,
  is_chill_category BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Category hierarchy and metadata'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.dim_category")

# COMMAND ----------

# MAGIC %md
# MAGIC ### dim_brand - Brand Master

# COMMAND ----------

# DBTITLE 1,Create dim_brand
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.dim_brand (
  brand_id STRING PRIMARY KEY,
  brand_name STRING NOT NULL,
  manufacturer_id STRING,
  brand_country STRING,
  is_private_label BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Brand master dimension'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.dim_brand")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Create Fact Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### fact_sales_weekly - Historical Sales

# COMMAND ----------

# DBTITLE 1,Create fact_sales_weekly
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.fact_sales_weekly (
  sale_id STRING PRIMARY KEY,
  store_id STRING NOT NULL,
  sku_id STRING NOT NULL,
  week_start_date DATE NOT NULL,
  units_sold INT,
  net_sales_value DECIMAL(15,2),
  regular_price DECIMAL(10,2),
  promo_price DECIMAL(10,2),
  promo_flag BOOLEAN,
  promo_type STRING,
  promo_discount_pct DECIMAL(5,2),
  on_display_flag BOOLEAN,
  on_promotion_flag BOOLEAN,
  availability_rate DECIMAL(5,2),
  out_of_stock_days INT,
  stock_at_week_start INT,
  stock_at_week_end INT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
PARTITIONED BY (week_start_date)
COMMENT 'Historical sales data at store × SKU × week grain'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.fact_sales_weekly")

# COMMAND ----------

# MAGIC %md
# MAGIC ### fact_planogram_current - Current Shelf Layout

# COMMAND ----------

# DBTITLE 1,Create fact_planogram_current
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.fact_planogram_current (
  planogram_id STRING PRIMARY KEY,
  store_id STRING NOT NULL,
  category_id STRING NOT NULL,
  sku_id STRING NOT NULL,
  shelf_id STRING,
  shelf_level INT,
  position_order INT,
  facings_horizontal INT,
  facings_vertical INT,
  facings_depth INT,
  total_facings INT,
  effective_width_mm INT,
  effective_height_mm INT,
  start_position_mm INT,
  end_position_mm INT,
  is_eye_level BOOLEAN,
  last_updated_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Current planogram and shelf layout'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.fact_planogram_current")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⚙️ Create Configuration Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### cfg_range_constraints - Range Rules

# COMMAND ----------

# DBTITLE 1,Create cfg_range_constraints
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.cfg_range_constraints (
  constraint_id STRING PRIMARY KEY,
  store_id STRING,
  planogram_cluster_id STRING,
  category_id STRING NOT NULL,
  min_range_size INT,
  max_range_size INT,
  min_facings_per_sku INT,
  max_facings_per_sku INT,
  min_private_label_share DECIMAL(5,2),
  max_any_brand_share DECIMAL(5,2),
  min_eye_level_share DECIMAL(5,2),
  forced_include_skus STRING,
  forced_exclude_skus STRING,
  valid_from_date DATE,
  valid_to_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Business rules for range breadth, facings, and assortment'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.cfg_range_constraints")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔄 Load Sample Data

# COMMAND ----------

# DBTITLE 1,Load Sample Categories
if LOAD_SAMPLE_DATA:
    print("🔄 Loading sample data...")
    
    now = datetime.now()
    
    # Sample Categories
    categories = [
        {"category_id": "CAT001", "category_name": "Beer & Seltzer", "department": "Liquor", 
         "parent_category_id": None, "category_role": "destination", "space_priority": 2, 
         "is_chill_category": True, "created_at": now, "updated_at": now},
        {"category_id": "CAT002", "category_name": "Hot Sauce", "department": "Grocery", 
         "parent_category_id": None, "category_role": "routine", "space_priority": 3, 
         "is_chill_category": False, "created_at": now, "updated_at": now},
        {"category_id": "CAT003", "category_name": "Ice Cream", "department": "Frozen", 
         "parent_category_id": None, "category_role": "destination", "space_priority": 1, 
         "is_chill_category": False, "created_at": now, "updated_at": now},
    ]
    
    categories_df = spark.createDataFrame(categories)
    categories_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_category")
    print(f"✅ Loaded {len(categories)} categories")
    
    # Sample Brands
    brands = [
        {"brand_id": "BRD001", "brand_name": "Stone & Wood", "manufacturer_id": "MFG001", 
         "brand_country": "Australia", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD002", "brand_name": "Balter", "manufacturer_id": "MFG002", 
         "brand_country": "Australia", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD003", "brand_name": "White Claw", "manufacturer_id": "MFG003", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD010", "brand_name": "Sriracha", "manufacturer_id": "MFG010", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD020", "brand_name": "Ben & Jerry's", "manufacturer_id": "MFG020", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
    ]
    
    brands_df = spark.createDataFrame(brands)
    brands_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_brand")
    print(f"✅ Loaded {len(brands)} brands")
    
    # Sample Stores
    stores = [
        {"store_id": "STORE001", "store_name": "Coles Docklands", "store_code": "COL-001", 
         "store_format": "supermarket", "store_size_sqm": 2500, "region_id": "REG001", 
         "region_name": "Victoria", "city": "Melbourne", "postcode": "3008", 
         "country": "Australia", "affluence_segment": "high", 
         "demographic_profile": "urban professionals", "opening_date": "2020-01-15", 
         "closing_date": None, "planogram_cluster_id": "CLUSTER001", 
         "created_at": now, "updated_at": now},
        {"store_id": "STORE002", "store_name": "Coles Spencer St", "store_code": "COL-002", 
         "store_format": "supermarket", "store_size_sqm": 2200, "region_id": "REG001", 
         "region_name": "Victoria", "city": "Melbourne", "postcode": "3000", 
         "country": "Australia", "affluence_segment": "medium", 
         "demographic_profile": "commuters", "opening_date": "2018-06-01", 
         "closing_date": None, "planogram_cluster_id": "CLUSTER001", 
         "created_at": now, "updated_at": now},
    ]
    
    stores_df = spark.createDataFrame(stores)
    stores_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_store")
    print(f"✅ Loaded {len(stores)} stores")
    
    # Get SKUs from existing dim_sku_staging
    print("📊 Generating sample sales data from existing SKUs...")
    sku_df = spark.table(f"{CATALOG}.{SCHEMA}.dim_sku_staging").toPandas()
    
    # Generate sales data (last 12 weeks)
    sales_data = []
    sale_id = 1
    for week_offset in range(12):
        week_start = datetime.now().date() - timedelta(weeks=12-week_offset)
        for store in stores:
            for _, sku in sku_df.iterrows():
                base_units = sku.get("WEEKLY_UNITS", 50)
                variance = np.random.normal(1.0, 0.15)
                units_sold = max(0, int(base_units * variance))
                unit_price = sku.get("UNIT_PRICE", 10.0)
                
                sales_data.append({
                    "sale_id": f"SALE{sale_id:08d}",
                    "store_id": store["store_id"],
                    "sku_id": sku["SKU_ID"],
                    "week_start_date": week_start,
                    "units_sold": units_sold,
                    "net_sales_value": float(units_sold * unit_price),
                    "regular_price": float(unit_price),
                    "promo_flag": False,
                    "availability_rate": 98.0,
                    "created_at": now,
                    "updated_at": now
                })
                sale_id += 1
    
    sales_df = spark.createDataFrame(sales_data)
    sales_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.fact_sales_weekly")
    print(f"✅ Loaded {len(sales_data)} sales records (12 weeks)")
    
    print("✅ Sample data loading complete!")
else:
    print("⏭️ Skipping sample data load")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Verify Schema

# COMMAND ----------

# DBTITLE 1,List All Tables
tables_df = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}")
display(tables_df)

# COMMAND ----------

# DBTITLE 1,Table Row Counts
table_names = [row.tableName for row in spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()]

print("="*60)
print("📊 TABLE STATISTICS")
print("="*60)

for table_name in sorted(table_names):
    try:
        count = spark.table(f"{CATALOG}.{SCHEMA}.{table_name}").count()
        print(f"  {table_name:40} {count:>8,} rows")
    except Exception as e:
        print(f"  {table_name:40} ERROR: {str(e)[:30]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Complete!
# MAGIC 
# MAGIC **Extended Delta Lake schema successfully!**
# MAGIC 
# MAGIC ### Your Architecture
# MAGIC 
# MAGIC ```
# MAGIC range_optimizer_catalog.range_optimizer (Lakebase/PostgreSQL)
# MAGIC   ├── dim_sku (FOREIGN TABLE)
# MAGIC   ├── demand_forecast (FOREIGN TABLE)
# MAGIC   ├── opt_recommended_planogram (FOREIGN TABLE)
# MAGIC   ├── optimization_runs (FOREIGN TABLE)
# MAGIC   └── stock_optimization_results (FOREIGN TABLE)
# MAGIC 
# MAGIC smarter_forecasting.stock_optimization (Delta Lake)
# MAGIC   ├── sku_features (MANAGED - Feature Store)
# MAGIC   ├── demand_features (MANAGED - Feature Store)
# MAGIC   ├── dim_sku_staging (MANAGED)
# MAGIC   ├── dim_store (MANAGED) ← NEW
# MAGIC   ├── dim_category (MANAGED) ← NEW
# MAGIC   ├── dim_brand (MANAGED) ← NEW
# MAGIC   ├── fact_sales_weekly (MANAGED) ← NEW
# MAGIC   ├── fact_planogram_current (MANAGED) ← NEW
# MAGIC   └── cfg_range_constraints (MANAGED) ← NEW
# MAGIC ```
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Query your data**: Use the new tables for analytics
# MAGIC 2. **Train models**: Feature tables are ready for ML
# MAGIC 3. **Run optimizations**: Complete schema supports full optimization workflow
