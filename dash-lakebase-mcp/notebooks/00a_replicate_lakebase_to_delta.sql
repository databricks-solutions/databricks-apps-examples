-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 🔄 Replicate Lakebase to Delta
-- MAGIC 
-- MAGIC This SQL notebook replicates data from **Lakebase (PostgreSQL)** to **Delta Lake** in Unity Catalog.
-- MAGIC 
-- MAGIC ## Why This is Needed
-- MAGIC 
-- MAGIC - **Lakebase** can ONLY be queried via **SQL Warehouse (DBSQL)** - not Spark compute clusters
-- MAGIC - **ML pipelines** require Spark compute for feature engineering and model training
-- MAGIC - **Solution**: Replicate Lakebase tables to Delta using CTAS (Create Table As Select)
-- MAGIC 
-- MAGIC ## Data Flow
-- MAGIC 
-- MAGIC ```
-- MAGIC Lakebase (range_optimizer_catalog.range_optimizer.*)
-- MAGIC     ↓  (via SQL Warehouse - this notebook)
-- MAGIC Delta Lake ({catalog}.{schema}.*_staging)
-- MAGIC     ↓  (via Spark compute)
-- MAGIC Feature Tables ({catalog}.{schema}.sku_features, demand_features)
-- MAGIC     ↓
-- MAGIC ML Training & Serving
-- MAGIC ```
-- MAGIC 
-- MAGIC ## Tables Replicated
-- MAGIC 
-- MAGIC | Lakebase Source | Delta Target | Purpose |
-- MAGIC |-----------------|--------------|---------|
-- MAGIC | `dim_sku` | `dim_sku_staging` | Product master for feature engineering |
-- MAGIC | `fact_sales_weekly` | `fact_sales_staging` | Historical sales for demand modeling |
-- MAGIC | `opt_recommended_planogram` | `opt_planogram_staging` | Latest optimization results |

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Configuration

-- COMMAND ----------

-- Set parameters
SET catalog = range_optimizer_catalog;
SET target_catalog = smarter_forecasting;
SET schema = range_optimizer;
SET target_schema = stock_optimization;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 1. Replicate dim_sku

-- COMMAND ----------

-- DBTITLE 1,Create dim_sku_staging from Lakebase
CREATE OR REPLACE TABLE ${target_catalog}.${target_schema}.dim_sku_staging
USING DELTA
COMMENT 'Staging copy of SKU master from Lakebase for Spark compute access'
AS
SELECT 
  sku_id,
  sku_name,
  brand_id,
  category_id,
  segment,
  pack_size,
  pack_size_uom,
  pack_width_mm,
  pack_depth_mm,
  pack_height_mm,
  is_private_label,
  is_must_stock,
  sku_status,
  weekly_units,
  unit_price,
  unit_cost,
  gross_margin_pct,
  current_facings,
  created_at,
  updated_at,
  CURRENT_TIMESTAMP() AS replicated_at
FROM ${catalog}.${schema}.dim_sku;

-- Verify row count
SELECT 'dim_sku_staging' AS table_name, COUNT(*) AS row_count 
FROM ${target_catalog}.${target_schema}.dim_sku_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 2. Replicate dim_category

-- COMMAND ----------

-- DBTITLE 1,Create dim_category_staging from Lakebase
CREATE OR REPLACE TABLE ${target_catalog}.${target_schema}.dim_category_staging
USING DELTA
COMMENT 'Staging copy of category master from Lakebase'
AS
SELECT 
  category_id,
  category_name,
  department,
  parent_category_id,
  category_role,
  space_priority,
  is_chill_category,
  created_at,
  updated_at,
  CURRENT_TIMESTAMP() AS replicated_at
FROM ${catalog}.${schema}.dim_category;

SELECT 'dim_category_staging' AS table_name, COUNT(*) AS row_count 
FROM ${target_catalog}.${target_schema}.dim_category_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3. Replicate dim_brand

-- COMMAND ----------

-- DBTITLE 1,Create dim_brand_staging from Lakebase
CREATE OR REPLACE TABLE ${target_catalog}.${target_schema}.dim_brand_staging
USING DELTA
COMMENT 'Staging copy of brand master from Lakebase'
AS
SELECT 
  brand_id,
  brand_name,
  manufacturer_id,
  brand_country,
  is_private_label,
  created_at,
  updated_at,
  CURRENT_TIMESTAMP() AS replicated_at
FROM ${catalog}.${schema}.dim_brand;

SELECT 'dim_brand_staging' AS table_name, COUNT(*) AS row_count 
FROM ${target_catalog}.${target_schema}.dim_brand_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 4. Replicate fact_sales_weekly (Last 52 Weeks)

-- COMMAND ----------

-- DBTITLE 1,Create fact_sales_staging from Lakebase
CREATE OR REPLACE TABLE ${target_catalog}.${target_schema}.fact_sales_staging
USING DELTA
PARTITIONED BY (week_start_date)
COMMENT 'Staging copy of sales facts from Lakebase (last 52 weeks)'
AS
SELECT 
  sale_id,
  store_id,
  sku_id,
  week_start_date,
  units_sold,
  net_sales_value,
  regular_price,
  promo_flag,
  promo_type,
  promo_discount_pct,
  availability_rate,
  created_at,
  updated_at,
  CURRENT_TIMESTAMP() AS replicated_at
FROM ${catalog}.${schema}.fact_sales_weekly
WHERE week_start_date >= DATE_SUB(CURRENT_DATE(), 365);

SELECT 'fact_sales_staging' AS table_name, COUNT(*) AS row_count 
FROM ${target_catalog}.${target_schema}.fact_sales_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 5. Replicate ml_demand_forecast

-- COMMAND ----------

-- DBTITLE 1,Create ml_demand_forecast_staging from Lakebase
CREATE OR REPLACE TABLE ${target_catalog}.${target_schema}.ml_demand_forecast_staging
USING DELTA
COMMENT 'Staging copy of demand forecasts from Lakebase'
AS
SELECT 
  forecast_id,
  store_id,
  planogram_cluster_id,
  sku_id,
  forecast_week_start_date,
  baseline_demand_units,
  demand_with_promo_units,
  demand_with_space_units,
  forecast_accuracy_mape,
  model_version,
  model_run_date,
  created_at,
  CURRENT_TIMESTAMP() AS replicated_at
FROM ${catalog}.${schema}.ml_demand_forecast
WHERE model_run_date >= DATE_SUB(CURRENT_DATE(), 90);

SELECT 'ml_demand_forecast_staging' AS table_name, COUNT(*) AS row_count 
FROM ${target_catalog}.${target_schema}.ml_demand_forecast_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 6. Replicate opt_recommended_planogram (Latest Run)

-- COMMAND ----------

-- DBTITLE 1,Create opt_planogram_staging from Lakebase
CREATE OR REPLACE TABLE ${target_catalog}.${target_schema}.opt_planogram_staging
USING DELTA
PARTITIONED BY (optimization_run_date)
COMMENT 'Staging copy of optimization results from Lakebase'
AS
SELECT 
  opt_planogram_id,
  optimization_run_id,
  store_id,
  planogram_cluster_id,
  category_id,
  sku_id,
  is_ranged_recommended,
  recommended_facings,
  expected_units_weekly,
  expected_sales_value_weekly,
  expected_margin_weekly,
  change_from_current,
  facings_change,
  optimization_run_date,
  created_at,
  CURRENT_TIMESTAMP() AS replicated_at
FROM ${catalog}.${schema}.opt_recommended_planogram
WHERE optimization_run_date >= DATE_SUB(CURRENT_DATE(), 30);

SELECT 'opt_planogram_staging' AS table_name, COUNT(*) AS row_count 
FROM ${target_catalog}.${target_schema}.opt_planogram_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## ✅ Verification

-- COMMAND ----------

-- DBTITLE 1,Summary of Replicated Tables
SELECT 
  'dim_sku_staging' AS table_name,
  COUNT(*) AS row_count,
  MAX(replicated_at) AS last_replicated
FROM ${target_catalog}.${target_schema}.dim_sku_staging

UNION ALL

SELECT 
  'dim_category_staging' AS table_name,
  COUNT(*) AS row_count,
  MAX(replicated_at) AS last_replicated
FROM ${target_catalog}.${target_schema}.dim_category_staging

UNION ALL

SELECT 
  'dim_brand_staging' AS table_name,
  COUNT(*) AS row_count,
  MAX(replicated_at) AS last_replicated
FROM ${target_catalog}.${target_schema}.dim_brand_staging

UNION ALL

SELECT 
  'fact_sales_staging' AS table_name,
  COUNT(*) AS row_count,
  MAX(replicated_at) AS last_replicated
FROM ${target_catalog}.${target_schema}.fact_sales_staging

UNION ALL

SELECT 
  'ml_demand_forecast_staging' AS table_name,
  COUNT(*) AS row_count,
  MAX(replicated_at) AS last_replicated
FROM ${target_catalog}.${target_schema}.ml_demand_forecast_staging

UNION ALL

SELECT 
  'opt_planogram_staging' AS table_name,
  COUNT(*) AS row_count,
  MAX(replicated_at) AS last_replicated
FROM ${target_catalog}.${target_schema}.opt_planogram_staging;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 🎉 Replication Complete!
-- MAGIC 
-- MAGIC **Data replicated from Lakebase to Delta Lake staging tables.**
-- MAGIC 
-- MAGIC ### Scheduling
-- MAGIC 
-- MAGIC To keep staging tables fresh, schedule this notebook as a Databricks Job:
-- MAGIC 
-- MAGIC 1. Create a SQL Warehouse-based job (required for Lakebase access)
-- MAGIC 2. Set schedule: Daily at 2:00 AM
-- MAGIC 3. Attach to a SQL Warehouse (not a compute cluster)
-- MAGIC 
-- MAGIC ### Next Steps
-- MAGIC 
-- MAGIC 1. Run `00_create_feature_tables.py` to create feature tables from staging
-- MAGIC 2. Run `01_train_stock_optimizer.py` for model training
-- MAGIC 3. Run `02_deploy_serving_endpoint.py` to deploy the model
