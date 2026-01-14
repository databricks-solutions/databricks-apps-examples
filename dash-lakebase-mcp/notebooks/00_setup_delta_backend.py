# Databricks notebook source
# MAGIC %md
# MAGIC # 🏗️ Setup Complete Delta Lake Backend for Range Optimizer
# MAGIC 
# MAGIC This notebook creates the **complete star schema** for the Range Optimizer in Unity Catalog using Delta Lake.
# MAGIC 
# MAGIC ## Architecture
# MAGIC 
# MAGIC **Star Schema Design** optimized for both:
# MAGIC - Transactional operations (loading, updating rules)
# MAGIC - Analytical queries (demand modeling, optimization preparation)
# MAGIC 
# MAGIC ## Tables Created
# MAGIC 
# MAGIC ### Dimensional Tables
# MAGIC - `dim_sku` - Product master
# MAGIC - `dim_store` - Store master
# MAGIC - `dim_category` - Category hierarchy
# MAGIC - `dim_brand` - Brand master
# MAGIC - `dim_time` - Time dimension
# MAGIC 
# MAGIC ### Fact Tables
# MAGIC - `fact_sales_weekly` - Historical sales data
# MAGIC - `fact_planogram_current` - Current shelf layout
# MAGIC - `fact_shelf_inventory` - Physical shelf constraints
# MAGIC 
# MAGIC ### Configuration Tables
# MAGIC - `cfg_range_constraints` - Range breadth and facings rules
# MAGIC - `cfg_merchandising_rules` - Advanced business rules
# MAGIC - `cfg_sku_cost_margin` - Cost and margin data (SCD Type 2)
# MAGIC 
# MAGIC ### Analytics Tables
# MAGIC - `agg_sku_performance_weekly` - Pre-aggregated SKU metrics
# MAGIC - `ml_demand_forecast` - Demand forecast outputs
# MAGIC 
# MAGIC ### Optimization Tables
# MAGIC - `opt_recommended_planogram` - Optimizer output
# MAGIC - `opt_optimization_run_summary` - Run metadata
# MAGIC - `opt_constraint_violations` - Constraint violations tracking

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Install Dependencies

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering -q

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Setup Widgets
# Define widgets for job parameters
dbutils.widgets.text("catalog", "range_optimizer_catalog", "Catalog Name")
dbutils.widgets.text("schema", "range_optimizer", "Schema Name")
dbutils.widgets.text("catalog_storage_location", 
                     "abfss://iceberg@stdavidokeeffeinterop02.dfs.core.windows.net/root/catalogs/range_optimizer_catalog",
                     "Catalog Storage Location")
dbutils.widgets.dropdown("load_sample_data", "true", ["true", "false"], "Load Sample Data")

# Get parameter values
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
CATALOG_STORAGE_LOCATION = dbutils.widgets.get("catalog_storage_location")
LOAD_SAMPLE_DATA = dbutils.widgets.get("load_sample_data") == "true"

print(f"📦 Catalog: {CATALOG}")
print(f"📊 Schema: {SCHEMA}")
print(f"📁 Storage: {CATALOG_STORAGE_LOCATION}")
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

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗄️ Create Unity Catalog & Schema

# COMMAND ----------

# DBTITLE 1,Create Catalog & Schema
# Create catalog with managed location
try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} MANAGED LOCATION '{CATALOG_STORAGE_LOCATION}'")
    print(f"✅ Created catalog {CATALOG} with managed location")
except Exception as e:
    if "already exists" in str(e).lower() or "CATALOG_ALREADY_EXISTS" in str(e):
        print(f"ℹ️ Catalog {CATALOG} already exists")
    else:
        print(f"⚠️ Could not create with managed location, trying without...")
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        print(f"✅ Created catalog {CATALOG}")

# Create schema
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ Created schema {CATALOG}.{SCHEMA}")

# Use the schema
spark.sql(f"USE {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Dimensional Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1. dim_sku - Product Master

# COMMAND ----------

# DBTITLE 1,Create dim_sku
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.dim_sku (
  sku_id STRING PRIMARY KEY,
  gtin_ean BIGINT,
  sku_name STRING NOT NULL,
  brand_id STRING NOT NULL,
  manufacturer_id STRING,
  category_id STRING NOT NULL,
  subcategory_id STRING,
  segment STRING,
  pack_size DECIMAL(10,2),
  pack_size_uom STRING,
  case_pack_qty INT,
  pack_width_mm DECIMAL(10,2),
  pack_depth_mm DECIMAL(10,2),
  pack_height_mm DECIMAL(10,2),
  pack_type STRING,
  shelf_life_days INT,
  is_private_label BOOLEAN,
  is_chilled BOOLEAN,
  is_frozen BOOLEAN,
  sku_status STRING,
  launch_date DATE,
  discontinue_date DATE,
  -- Additional fields from sample_data
  weekly_units INT,
  unit_price DECIMAL(10,2),
  unit_cost DECIMAL(10,2),
  gross_margin_pct DECIMAL(5,2),
  current_facings INT,
  is_must_stock BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Product master dimension with SKU attributes and metrics'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.dim_sku")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2. dim_store - Store Master

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
# MAGIC ### 3. dim_category - Category Hierarchy

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
# MAGIC ### 4. dim_brand - Brand Master

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
# MAGIC ### 5. dim_time - Time Dimension

# COMMAND ----------

# DBTITLE 1,Create dim_time
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.dim_time (
  time_id INT PRIMARY KEY,
  date_key DATE NOT NULL,
  week_start_date DATE,
  week_end_date DATE,
  month_start_date DATE,
  month INT,
  quarter INT,
  year INT,
  is_holiday BOOLEAN,
  holiday_name STRING
)
USING DELTA
COMMENT 'Time dimension for time-series analysis'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.dim_time")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Fact Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6. fact_sales_weekly - Historical Sales

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
# MAGIC ### 7. fact_planogram_current - Current Shelf Layout

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
# MAGIC ### 8. fact_shelf_inventory - Shelf Space Constraints

# COMMAND ----------

# DBTITLE 1,Create fact_shelf_inventory
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.fact_shelf_inventory (
  shelf_inventory_id STRING PRIMARY KEY,
  store_id STRING NOT NULL,
  category_id STRING NOT NULL,
  shelf_id STRING,
  shelf_level INT,
  total_width_mm INT,
  total_height_mm INT,
  total_depth_mm INT,
  max_weight_kg INT,
  is_chilled BOOLEAN,
  current_utilized_width_mm INT,
  current_available_width_mm INT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Physical shelf space constraints and utilization'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.fact_shelf_inventory")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⚙️ Configuration Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### 9. cfg_range_constraints - Range Rules

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
# MAGIC ### 10. cfg_merchandising_rules - Advanced Business Rules

# COMMAND ----------

# DBTITLE 1,Create cfg_merchandising_rules
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.cfg_merchandising_rules (
  rule_id STRING PRIMARY KEY,
  rule_name STRING NOT NULL,
  rule_type STRING,
  scope_store_id STRING,
  scope_cluster_id STRING,
  scope_category_id STRING NOT NULL,
  scope_brand_id STRING,
  scope_segment STRING,
  scope_sku_id STRING,
  parameter_1 STRING,
  parameter_1_value DECIMAL(10,2),
  parameter_2 STRING,
  parameter_2_value DECIMAL(10,2),
  priority INT,
  is_active BOOLEAN,
  valid_from_date DATE,
  valid_to_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Advanced merchandising rules (brand blocking, adjacency, etc.)'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.cfg_merchandising_rules")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 11. cfg_sku_cost_margin - Cost & Margin Data (SCD Type 2)

# COMMAND ----------

# DBTITLE 1,Create cfg_sku_cost_margin
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.cfg_sku_cost_margin (
  cost_margin_id STRING PRIMARY KEY,
  sku_id STRING NOT NULL,
  vendor_id STRING,
  cost_price DECIMAL(10,2),
  regular_retail_price DECIMAL(10,2),
  suggested_promo_price DECIMAL(10,2),
  gross_margin_pct DECIMAL(5,2),
  contribution_margin DECIMAL(10,2),
  slotting_fee DECIMAL(10,2),
  minimum_order_qty INT,
  order_multiple INT,
  lead_time_days INT,
  valid_from_date DATE NOT NULL,
  valid_to_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'SKU cost and margin data with SCD Type 2 versioning'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.cfg_sku_cost_margin")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Analytics Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### 12. agg_sku_performance_weekly - Pre-aggregated SKU Metrics

# COMMAND ----------

# DBTITLE 1,Create agg_sku_performance_weekly
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.agg_sku_performance_weekly (
  perf_id STRING PRIMARY KEY,
  sku_id STRING NOT NULL,
  week_start_date DATE NOT NULL,
  total_units_sold INT,
  total_sales_value DECIMAL(15,2),
  avg_price DECIMAL(10,2),
  promo_lift_pct DECIMAL(5,2),
  stores_in_range_count INT,
  avg_availability_rate DECIMAL(5,2),
  segment_rank INT,
  created_at TIMESTAMP
)
USING DELTA
PARTITIONED BY (week_start_date)
COMMENT 'Pre-aggregated SKU performance metrics for dashboards'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.agg_sku_performance_weekly")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 13. ml_demand_forecast - Demand Forecast Outputs

# COMMAND ----------

# DBTITLE 1,Create ml_demand_forecast
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.ml_demand_forecast (
  forecast_id STRING PRIMARY KEY,
  store_id STRING,
  planogram_cluster_id STRING,
  sku_id STRING NOT NULL,
  forecast_week_start_date DATE,
  baseline_demand_units INT,
  demand_with_promo_units INT,
  demand_with_space_units INT,
  forecast_accuracy_mape DECIMAL(5,2),
  model_version STRING,
  model_run_date DATE,
  created_at TIMESTAMP
)
USING DELTA
PARTITIONED BY (model_run_date)
COMMENT 'Demand forecast outputs from ML models'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.ml_demand_forecast")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Optimization Tables

# COMMAND ----------

# MAGIC %md
# MAGIC ### 14. opt_recommended_planogram - Optimizer Output

# COMMAND ----------

# DBTITLE 1,Create opt_recommended_planogram
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.opt_recommended_planogram (
  opt_planogram_id STRING PRIMARY KEY,
  optimization_run_id STRING NOT NULL,
  store_id STRING,
  planogram_cluster_id STRING,
  category_id STRING NOT NULL,
  sku_id STRING NOT NULL,
  is_ranged_recommended BOOLEAN,
  recommended_facings INT,
  recommended_shelf_level INT,
  recommended_position_order INT,
  expected_units_weekly INT,
  expected_sales_value_weekly DECIMAL(15,2),
  expected_margin_weekly DECIMAL(15,2),
  change_from_current STRING,
  facings_change INT,
  execution_difficulty STRING,
  optimization_run_date DATE,
  valid_from_date DATE,
  created_at TIMESTAMP
)
USING DELTA
PARTITIONED BY (optimization_run_date)
COMMENT 'Recommended planogram from HiGHS optimizer'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.opt_recommended_planogram")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 15. opt_optimization_run_summary - Run Metadata

# COMMAND ----------

# DBTITLE 1,Create opt_optimization_run_summary
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.opt_optimization_run_summary (
  optimization_run_id STRING PRIMARY KEY,
  run_name STRING,
  scenario_type STRING,
  stores_included INT,
  categories_included INT,
  clusters_optimized INT,
  objective_value DECIMAL(20,2),
  total_expected_revenue DECIMAL(20,2),
  total_expected_margin DECIMAL(20,2),
  changes_sku_adds INT,
  changes_sku_removes INT,
  changes_sku_facings_changes INT,
  solver_name STRING,
  solver_status STRING,
  solver_time_seconds DECIMAL(10,2),
  model_version STRING,
  run_timestamp TIMESTAMP NOT NULL,
  run_date DATE,
  created_by STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Metadata about each optimization execution'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.opt_optimization_run_summary")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 16. opt_constraint_violations - Constraint Violations

# COMMAND ----------

# DBTITLE 1,Create opt_constraint_violations
spark.sql(f"""
CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.opt_constraint_violations (
  violation_id STRING PRIMARY KEY,
  optimization_run_id STRING NOT NULL,
  store_id STRING,
  category_id STRING,
  constraint_type STRING,
  constraint_name STRING,
  violation_magnitude DECIMAL(15,2),
  severity STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Constraint violations from optimization runs'
""")

print(f"✅ Created table: {CATALOG}.{SCHEMA}.opt_constraint_violations")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔄 Load Sample Data

# COMMAND ----------

# DBTITLE 1,Define Sample Data (from sample_data.py)
# Sample data aligned with mcp_app/range_optimizer/backend/sample_data.py
SAMPLE_SKUS = [
    # Beer & Seltzer (15 products)
    {"sku_id": "SKU3001", "sku_name": "Stone & Wood Pacific Ale 6pk", "brand_id": "BRD001", "category_id": "CAT001", "segment": "Craft Beer", "pack_size": 1980, "pack_size_uom": "ml", "pack_width_mm": 180, "weekly_units": 85, "unit_price": 24.00, "unit_cost": 14.40, "gross_margin_pct": 40, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU3002", "sku_name": "Stone & Wood Green Coast Lager 6pk", "brand_id": "BRD001", "category_id": "CAT001", "segment": "Craft Beer", "pack_size": 1980, "pack_size_uom": "ml", "pack_width_mm": 180, "weekly_units": 65, "unit_price": 23.00, "unit_cost": 13.80, "gross_margin_pct": 40, "current_facings": 2, "is_private_label": False, "is_must_stock": False, "sku_status": "active"},
    {"sku_id": "SKU3003", "sku_name": "Balter XPA 4pk", "brand_id": "BRD002", "category_id": "CAT001", "segment": "Craft Beer", "pack_size": 1500, "pack_size_uom": "ml", "pack_width_mm": 150, "weekly_units": 95, "unit_price": 22.00, "unit_cost": 13.20, "gross_margin_pct": 40, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU3004", "sku_name": "Balter Captain Sensible 4pk", "brand_id": "BRD002", "category_id": "CAT001", "segment": "Craft Beer", "pack_size": 1500, "pack_size_uom": "ml", "pack_width_mm": 150, "weekly_units": 55, "unit_price": 20.00, "unit_cost": 12.00, "gross_margin_pct": 40, "current_facings": 2, "is_private_label": False, "is_must_stock": False, "sku_status": "active"},
    {"sku_id": "SKU3009", "sku_name": "White Claw Variety 12pk", "brand_id": "BRD003", "category_id": "CAT001", "segment": "Hard Seltzer", "pack_size": 3960, "pack_size_uom": "ml", "pack_width_mm": 260, "weekly_units": 120, "unit_price": 32.00, "unit_cost": 17.60, "gross_margin_pct": 45, "current_facings": 4, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    
    # Hot Sauce (5 products)
    {"sku_id": "SKU4001", "sku_name": "Sriracha Original 455ml", "brand_id": "BRD010", "category_id": "CAT002", "segment": "Asian Style", "pack_size": 455, "pack_size_uom": "ml", "pack_width_mm": 80, "weekly_units": 145, "unit_price": 6.50, "unit_cost": 2.93, "gross_margin_pct": 55, "current_facings": 4, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU4003", "sku_name": "Tabasco Original 150ml", "brand_id": "BRD011", "category_id": "CAT002", "segment": "Louisiana Style", "pack_size": 150, "pack_size_uom": "ml", "pack_width_mm": 50, "weekly_units": 110, "unit_price": 5.00, "unit_cost": 2.25, "gross_margin_pct": 55, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU4005", "sku_name": "Cholula Original 150ml", "brand_id": "BRD012", "category_id": "CAT002", "segment": "Mexican Style", "pack_size": 150, "pack_size_uom": "ml", "pack_width_mm": 55, "weekly_units": 95, "unit_price": 5.50, "unit_cost": 2.75, "gross_margin_pct": 50, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU4007", "sku_name": "Frank's RedHot Original 354ml", "brand_id": "BRD013", "category_id": "CAT002", "segment": "Louisiana Style", "pack_size": 354, "pack_size_uom": "ml", "pack_width_mm": 70, "weekly_units": 85, "unit_price": 6.00, "unit_cost": 2.70, "gross_margin_pct": 55, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU4010", "sku_name": "Sambal Oelek Chili Paste 226g", "brand_id": "BRD014", "category_id": "CAT002", "segment": "Asian Style", "pack_size": 226, "pack_size_uom": "g", "pack_width_mm": 75, "weekly_units": 80, "unit_price": 4.50, "unit_cost": 2.03, "gross_margin_pct": 55, "current_facings": 2, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    
    # Ice Cream (5 products)
    {"sku_id": "SKU5001", "sku_name": "Ben & Jerry's Cookie Dough 458ml", "brand_id": "BRD020", "category_id": "CAT003", "segment": "Premium Pints", "pack_size": 458, "pack_size_uom": "ml", "pack_width_mm": 110, "weekly_units": 90, "unit_price": 13.50, "unit_cost": 6.75, "gross_margin_pct": 50, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU5002", "sku_name": "Ben & Jerry's Phish Food 458ml", "brand_id": "BRD020", "category_id": "CAT003", "segment": "Premium Pints", "pack_size": 458, "pack_size_uom": "ml", "pack_width_mm": 110, "weekly_units": 75, "unit_price": 13.50, "unit_cost": 6.75, "gross_margin_pct": 50, "current_facings": 2, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU5004", "sku_name": "Häagen-Dazs Salted Caramel 457ml", "brand_id": "BRD021", "category_id": "CAT003", "segment": "Premium Pints", "pack_size": 457, "pack_size_uom": "ml", "pack_width_mm": 110, "weekly_units": 70, "unit_price": 14.00, "unit_cost": 7.00, "gross_margin_pct": 50, "current_facings": 2, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU5006", "sku_name": "Häagen-Dazs Vanilla 457ml", "brand_id": "BRD021", "category_id": "CAT003", "segment": "Premium Pints", "pack_size": 457, "pack_size_uom": "ml", "pack_width_mm": 110, "weekly_units": 80, "unit_price": 14.00, "unit_cost": 7.00, "gross_margin_pct": 50, "current_facings": 2, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
    {"sku_id": "SKU5013", "sku_name": "Bulla Creamy Classics Vanilla 2L", "brand_id": "BRD022", "category_id": "CAT003", "segment": "Family Tubs", "pack_size": 2000, "pack_size_uom": "ml", "pack_width_mm": 180, "weekly_units": 85, "unit_price": 8.00, "unit_cost": 4.00, "gross_margin_pct": 50, "current_facings": 3, "is_private_label": False, "is_must_stock": True, "sku_status": "active"},
]

SAMPLE_CATEGORIES = [
    {"category_id": "CAT001", "category_name": "Beer & Seltzer", "department": "Liquor", "parent_category_id": None, "category_role": "destination", "space_priority": 2, "is_chill_category": True},
    {"category_id": "CAT002", "category_name": "Hot Sauce", "department": "Grocery", "parent_category_id": None, "category_role": "routine", "space_priority": 3, "is_chill_category": False},
    {"category_id": "CAT003", "category_name": "Ice Cream", "department": "Frozen", "parent_category_id": None, "category_role": "destination", "space_priority": 1, "is_chill_category": False},
]

SAMPLE_BRANDS = [
    {"brand_id": "BRD001", "brand_name": "Stone & Wood", "manufacturer_id": "MFG001", "brand_country": "Australia", "is_private_label": False},
    {"brand_id": "BRD002", "brand_name": "Balter", "manufacturer_id": "MFG002", "brand_country": "Australia", "is_private_label": False},
    {"brand_id": "BRD003", "brand_name": "White Claw", "manufacturer_id": "MFG003", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD010", "brand_name": "Sriracha", "manufacturer_id": "MFG010", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD011", "brand_name": "Tabasco", "manufacturer_id": "MFG011", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD012", "brand_name": "Cholula", "manufacturer_id": "MFG012", "brand_country": "Mexico", "is_private_label": False},
    {"brand_id": "BRD013", "brand_name": "Frank's", "manufacturer_id": "MFG013", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD014", "brand_name": "Huy Fong", "manufacturer_id": "MFG014", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD020", "brand_name": "Ben & Jerry's", "manufacturer_id": "MFG020", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD021", "brand_name": "Häagen-Dazs", "manufacturer_id": "MFG021", "brand_country": "USA", "is_private_label": False},
    {"brand_id": "BRD022", "brand_name": "Bulla", "manufacturer_id": "MFG022", "brand_country": "Australia", "is_private_label": False},
]

SAMPLE_STORES = [
    {"store_id": "STORE001", "store_name": "Coles Docklands", "store_code": "COL-001", "store_format": "supermarket", "store_size_sqm": 2500, "region_id": "REG001", "region_name": "Victoria", "city": "Melbourne", "postcode": "3008", "country": "Australia", "affluence_segment": "high", "demographic_profile": "urban professionals", "opening_date": "2020-01-15", "closing_date": None, "planogram_cluster_id": "CLUSTER001"},
    {"store_id": "STORE002", "store_name": "Coles Spencer St", "store_code": "COL-002", "store_format": "supermarket", "store_size_sqm": 2200, "region_id": "REG001", "region_name": "Victoria", "city": "Melbourne", "postcode": "3000", "country": "Australia", "affluence_segment": "medium", "demographic_profile": "commuters", "opening_date": "2018-06-01", "closing_date": None, "planogram_cluster_id": "CLUSTER001"},
]

print(f"📦 Defined {len(SAMPLE_SKUS)} sample SKUs")
print(f"📁 Defined {len(SAMPLE_CATEGORIES)} sample categories")
print(f"🏷️ Defined {len(SAMPLE_BRANDS)} sample brands")
print(f"🏪 Defined {len(SAMPLE_STORES)} sample stores")

# COMMAND ----------

# DBTITLE 1,Load Sample Data into Tables
if LOAD_SAMPLE_DATA:
    print("🔄 Loading sample data...")
    
    # Add timestamps
    now = datetime.now()
    
    # Load Categories
    categories_df = spark.createDataFrame([
        {**cat, "created_at": now, "updated_at": now} 
        for cat in SAMPLE_CATEGORIES
    ])
    categories_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_category")
    print(f"✅ Loaded {len(SAMPLE_CATEGORIES)} categories")
    
    # Load Brands
    brands_df = spark.createDataFrame([
        {**brand, "created_at": now, "updated_at": now} 
        for brand in SAMPLE_BRANDS
    ])
    brands_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_brand")
    print(f"✅ Loaded {len(SAMPLE_BRANDS)} brands")
    
    # Load SKUs
    skus_df = spark.createDataFrame([
        {
            **sku,
            "gtin_ean": None,
            "manufacturer_id": sku["brand_id"].replace("BRD", "MFG"),  # Derive manufacturer from brand
            "subcategory_id": None,
            "case_pack_qty": 12,
            "pack_depth_mm": None,
            "pack_height_mm": None,
            "pack_type": "box",
            "shelf_life_days": 365,
            "is_chilled": sku.get("category_id") == "CAT001",  # Beer is chilled
            "is_frozen": sku.get("category_id") == "CAT003",  # Ice cream is frozen
            "launch_date": None,
            "discontinue_date": None,
            "created_at": now,
            "updated_at": now
        } 
        for sku in SAMPLE_SKUS
    ])
    skus_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_sku")
    print(f"✅ Loaded {len(SAMPLE_SKUS)} SKUs")
    
    # Load Stores
    stores_df = spark.createDataFrame([
        {**store, "created_at": now, "updated_at": now} 
        for store in SAMPLE_STORES
    ])
    stores_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.dim_store")
    print(f"✅ Loaded {len(SAMPLE_STORES)} stores")
    
    # Generate sample sales data (last 52 weeks)
    print("📊 Generating sample sales data...")
    sales_data = []
    sale_id = 1
    for week_offset in range(52):
        week_start = datetime.now().date() - timedelta(weeks=52-week_offset)
        for store in SAMPLE_STORES:
            for sku in SAMPLE_SKUS:
                # Add some variance to weekly units
                base_units = sku["weekly_units"]
                variance = np.random.normal(1.0, 0.15)  # 15% std dev
                units_sold = max(0, int(base_units * variance))
                
                sales_data.append({
                    "sale_id": f"SALE{sale_id:08d}",
                    "store_id": store["store_id"],
                    "sku_id": sku["sku_id"],
                    "week_start_date": week_start,
                    "units_sold": units_sold,
                    "net_sales_value": units_sold * sku["unit_price"],
                    "regular_price": sku["unit_price"],
                    "promo_price": None,
                    "promo_flag": False,
                    "promo_type": None,
                    "promo_discount_pct": None,
                    "on_display_flag": False,
                    "on_promotion_flag": False,
                    "availability_rate": 98.0,
                    "out_of_stock_days": 0,
                    "stock_at_week_start": base_units * 4,
                    "stock_at_week_end": base_units * 3,
                    "created_at": now,
                    "updated_at": now
                })
                sale_id += 1
    
    sales_df = spark.createDataFrame(sales_data)
    sales_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.fact_sales_weekly")
    print(f"✅ Loaded {len(sales_data)} sales records (52 weeks)")
    
    # Generate demand forecasts
    print("📈 Generating demand forecasts...")
    forecast_data = []
    for sku in SAMPLE_SKUS:
        forecast_data.append({
            "forecast_id": f"FCST_{sku['sku_id']}",
            "store_id": None,  # Cluster-level forecast
            "planogram_cluster_id": "CLUSTER001",
            "sku_id": sku["sku_id"],
            "forecast_week_start_date": datetime.now().date(),
            "baseline_demand_units": sku["weekly_units"],
            "demand_with_promo_units": int(sku["weekly_units"] * 1.3),  # 30% uplift
            "demand_with_space_units": int(sku["weekly_units"] * 1.1),  # 10% space elasticity
            "forecast_accuracy_mape": round(np.random.uniform(8, 15), 2),
            "model_version": "v1.0",
            "model_run_date": datetime.now().date(),
            "created_at": now
        })
    
    forecast_df = spark.createDataFrame(forecast_data)
    forecast_df.write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.ml_demand_forecast")
    print(f"✅ Loaded {len(forecast_data)} demand forecasts")
    
    print("✅ Sample data loading complete!")
else:
    print("⏭️ Skipping sample data load (set load_sample_data=true to load)")

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
    count = spark.table(f"{CATALOG}.{SCHEMA}.{table_name}").count()
    print(f"  {table_name:40} {count:>8,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Sample Queries

# COMMAND ----------

# DBTITLE 1,SKU Performance Summary
spark.sql(f"""
SELECT 
  s.sku_id,
  s.sku_name,
  b.brand_name,
  c.category_name,
  s.segment,
  SUM(f.units_sold) AS total_units_52w,
  SUM(f.net_sales_value) AS total_sales_52w,
  ROUND(SUM(f.net_sales_value) / NULLIF(SUM(f.units_sold), 0), 2) AS avg_price,
  COUNT(DISTINCT f.store_id) AS stores_in_range,
  ROUND(AVG(f.availability_rate), 1) AS avg_availability_pct
FROM {CATALOG}.{SCHEMA}.dim_sku s
LEFT JOIN {CATALOG}.{SCHEMA}.dim_brand b ON s.brand_id = b.brand_id
LEFT JOIN {CATALOG}.{SCHEMA}.dim_category c ON s.category_id = c.category_id
LEFT JOIN {CATALOG}.{SCHEMA}.fact_sales_weekly f ON s.sku_id = f.sku_id
WHERE f.week_start_date >= DATE_SUB(CURRENT_DATE(), 365)
GROUP BY s.sku_id, s.sku_name, b.brand_name, c.category_name, s.segment
ORDER BY total_sales_52w DESC
LIMIT 20
""").display()

# COMMAND ----------

# DBTITLE 1,Category Performance
spark.sql(f"""
SELECT 
  c.category_name,
  COUNT(DISTINCT s.sku_id) AS sku_count,
  SUM(f.units_sold) AS total_units,
  SUM(f.net_sales_value) AS total_sales,
  ROUND(AVG(s.gross_margin_pct), 1) AS avg_margin_pct
FROM {CATALOG}.{SCHEMA}.dim_category c
JOIN {CATALOG}.{SCHEMA}.dim_sku s ON c.category_id = s.category_id
LEFT JOIN {CATALOG}.{SCHEMA}.fact_sales_weekly f ON s.sku_id = f.sku_id
WHERE f.week_start_date >= DATE_SUB(CURRENT_DATE(), 90)
GROUP BY c.category_name
ORDER BY total_sales DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Complete!
# MAGIC 
# MAGIC **Delta Lake backend created successfully!**
# MAGIC 
# MAGIC ### Schema Summary
# MAGIC 
# MAGIC | Category | Tables | Purpose |
# MAGIC |----------|--------|---------|
# MAGIC | Dimensions | 5 tables | Product, store, category, brand, time |
# MAGIC | Facts | 3 tables | Sales, planogram, shelf inventory |
# MAGIC | Configuration | 3 tables | Range constraints, merchandising rules, cost/margin |
# MAGIC | Analytics | 2 tables | SKU performance, demand forecasts |
# MAGIC | Optimization | 3 tables | Recommended planogram, run summary, violations |
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Create Feature Tables**: Run `00_create_feature_tables.py` to set up ML feature tables
# MAGIC 2. **Train Model**: Run `01_train_stock_optimizer.py` to train optimization model
# MAGIC 3. **Deploy Endpoint**: Run `02_deploy_serving_endpoint.py` to create serving endpoint
# MAGIC 4. **Configure MCP App**: Update MCP app to read from these Unity Catalog tables
# MAGIC 
# MAGIC ### Data Flow
# MAGIC 
# MAGIC ```
# MAGIC Delta Lake (Unity Catalog)
# MAGIC     ├── Dimensional Data (dim_*)
# MAGIC     ├── Historical Sales (fact_sales_weekly)
# MAGIC     ├── Current State (fact_planogram_current)
# MAGIC     ├── Business Rules (cfg_*)
# MAGIC     ↓
# MAGIC Feature Engineering
# MAGIC     ↓
# MAGIC ML Model Training
# MAGIC     ↓
# MAGIC Optimization (HiGHS)
# MAGIC     ↓
# MAGIC Recommendations (opt_recommended_planogram)
# MAGIC ```
