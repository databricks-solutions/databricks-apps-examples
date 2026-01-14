-- Replicate Lakebase data to Delta tables for ML training
-- This must run on a SQL Warehouse (serverless SQL) since Lakebase only supports DBSQL

-- Create target catalog and schema if not exists
CREATE CATALOG IF NOT EXISTS ${catalog} 
  MANAGED LOCATION '${catalog_storage_location}';

CREATE SCHEMA IF NOT EXISTS ${catalog}.${schema};

-- Drop and recreate staging table from Lakebase
DROP TABLE IF EXISTS ${catalog}.${schema}.dim_sku_staging;

CREATE TABLE ${catalog}.${schema}.dim_sku_staging AS
SELECT 
    SKU_ID,
    SKU_NAME,
    BRAND,
    CATEGORY,
    SEGMENT,
    PACK_SIZE,
    PACK_WIDTH_MM,
    UNIT_PRICE,
    UNIT_COST,
    GROSS_MARGIN_PCT,
    WEEKLY_UNITS,
    CURRENT_FACINGS,
    IS_PRIVATE_LABEL,
    IS_MUST_STOCK,
    STATUS,
    current_timestamp() as REPLICATED_AT
FROM range_optimizer_catalog.range_optimizer.dim_sku;

-- Show results
SELECT 
    COUNT(*) as total_skus,
    COUNT(DISTINCT CATEGORY) as categories,
    SUM(WEEKLY_UNITS) as total_weekly_units
FROM ${catalog}.${schema}.dim_sku_staging;
