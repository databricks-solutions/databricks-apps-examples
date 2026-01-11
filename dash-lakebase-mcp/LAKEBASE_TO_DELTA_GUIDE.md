# 🔄 Lakebase to Delta Replication Guide

Complete guide for replicating data from **Databricks Lakebase** (PostgreSQL) to **Delta Lake** using the official Databricks approach.

## Overview

This guide follows the **official Databricks documentation** for Lakebase-to-Delta replication:

1. **Register Lakebase database** as a read-only Unity Catalog catalog (one-time setup)
2. **Query the registered catalog** and replicate to Delta tables (scheduled or on-demand)

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│ Step 1: Register Lakebase in Unity Catalog (One-Time)     │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────┐
    │ Lakebase PostgreSQL                             │
    │  Instance: daveok                               │
    │  Database: databricks_postgres                  │
    │  Schema: range_optimizer                        │
    │    └── sku_data (source table)                  │
    └─────────────────────────────────────────────────┘
                            │
                  ┌─────────┴─────────┐
                  │ Register as UC    │
                  │ Catalog (read-    │
                  │ only foreign cat) │
                  └─────────┬─────────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────┐
    │ Unity Catalog                                   │
    │  Catalog: range_optimizer_catalog (read-only)   │
    │  Schema: range_optimizer                        │
    │    └── sku_data (federated table)               │
    └─────────────────────────────────────────────────┘
                            │
┌────────────────────────────────────────────────────────────┐
│ Step 2: Replicate to Delta (Scheduled/On-Demand)          │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │ CTAS or MERGE   │
                  │ (this notebook) │
                  └─────────┬───────┘
                            │
                            ▼
    ┌─────────────────────────────────────────────────┐
    │ Delta Lake (Unity Catalog)                      │
    │  Catalog: main                                  │
    │  Schema: range_optimizer                        │
    │    └── delta_sku_data (Delta table)             │
    └─────────────────────────────────────────────────┘
```

## Prerequisites

- ✅ Databricks workspace with Unity Catalog enabled
- ✅ Lakebase Autoscaling or Provisioned instance
- ✅ `CREATE CATALOG` permission on Unity Catalog metastore
- ✅ Serverless SQL warehouse or cluster with Unity Catalog

## Step 1: Register Lakebase Database (One-Time Setup)

### Option A: Using Databricks UI (Recommended)

1. **Navigate to Catalog Explorer**
   - In your Databricks workspace, click **Catalog** in the sidebar

2. **Create a new catalog**
   - Click the **+** icon → **Create a catalog**

3. **Configure the catalog**
   - **Catalog name**: `range_optimizer_catalog`
   - **Catalog type**: Select **Lakebase Postgres**
   - **Version**: Choose **Autoscaling** (or Provisioned if you're using that)

4. **Select Lakebase connection**
   - **Project**: Select your Lakebase project
   - **Branch**: `main` (or your target branch)
   - **Postgres database**: `databricks_postgres`

5. **Create**
   - Click **Create** to register the catalog

6. **Verify**
   - Browse the catalog in Catalog Explorer
   - You should see your schemas and tables

### Option B: Using Python SDK

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import CreateCatalog

w = WorkspaceClient()

# Register Lakebase database as Unity Catalog catalog
catalog = w.catalogs.create(
    name="range_optimizer_catalog",
    comment="Read-only catalog for Lakebase daveok instance",
    connection_name="daveok",  # Your Lakebase instance name
    options={
        "database": "databricks_postgres"
    }
)

print(f"✅ Registered catalog: {catalog.name}")
```

### Option C: Using SQL (if connection exists)

```sql
CREATE FOREIGN CATALOG range_optimizer_catalog
USING CONNECTION daveok
OPTIONS (database = 'databricks_postgres');
```

### Verify Registration

```sql
-- List all catalogs
SHOW CATALOGS;

-- List schemas in the registered catalog
SHOW SCHEMAS IN range_optimizer_catalog;

-- List tables in a schema
SHOW TABLES IN range_optimizer_catalog.range_optimizer;

-- Query the registered table (read-only)
SELECT * FROM range_optimizer_catalog.range_optimizer.sku_data LIMIT 10;
```

## Step 2: Replicate to Delta Lake

Once the Lakebase database is registered as a Unity Catalog catalog, you can query it like any other Unity Catalog table and replicate to Delta.

### Method 1: Full Refresh (CTAS)

Best for: Complete table replacement, when most data changes

```sql
-- Create or replace Delta table with all data from Lakebase
CREATE OR REPLACE TABLE main.range_optimizer.delta_sku_data
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'description' = 'Replicated from Lakebase range_optimizer.sku_data'
)
AS SELECT 
    *,
    current_timestamp() as _replicated_at
FROM range_optimizer_catalog.range_optimizer.sku_data;
```

### Method 2: Incremental Sync (MERGE)

Best for: Ongoing replication, only sync changed rows

```sql
-- First run: Create table if it doesn't exist
CREATE TABLE IF NOT EXISTS main.range_optimizer.delta_sku_data
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true'
)
AS SELECT 
    *,
    current_timestamp() as _replicated_at
FROM range_optimizer_catalog.range_optimizer.sku_data;

-- Subsequent runs: MERGE changed rows
MERGE INTO main.range_optimizer.delta_sku_data AS target
USING (
    SELECT 
        *,
        current_timestamp() as _replicated_at
    FROM range_optimizer_catalog.range_optimizer.sku_data
    WHERE UPDATED_AT > (
        SELECT MAX(UPDATED_AT) FROM main.range_optimizer.delta_sku_data
    )
) AS source
ON target.SELL_ID = source.SELL_ID
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

### Method 3: Using Python (PySpark)

```python
# Read from registered Lakebase catalog
source_df = spark.table("range_optimizer_catalog.range_optimizer.sku_data")

# Add replication metadata
from pyspark.sql.functions import current_timestamp
replicated_df = source_df.withColumn("_replicated_at", current_timestamp())

# Write to Delta (full refresh)
replicated_df.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("main.range_optimizer.delta_sku_data")

print("✅ Replication completed")
```

## Step 3: Schedule Automated Replication

### Option A: Databricks Workflow (Recommended)

Create a workflow to run the replication notebook on a schedule:

```bash
databricks jobs create --json '{
  "name": "Lakebase to Delta - SKU Data Replication",
  "tasks": [{
    "task_key": "replicate_sku_data",
    "notebook_task": {
      "notebook_path": "/Workspace/Users/your-email@domain.com/notebooks/04_replicate_lakebase_to_delta",
      "base_parameters": {
        "REPLICATION_MODE": "incremental"
      }
    },
    "existing_cluster_id": "your-cluster-id"
  }],
  "schedule": {
    "quartz_cron_expression": "0 */4 * * * ?",
    "timezone_id": "UTC",
    "pause_status": "UNPAUSED"
  },
  "email_notifications": {
    "on_failure": ["your-email@domain.com"]
  }
}'
```

**Schedule Examples:**
- Every hour: `0 * * * * ?`
- Every 4 hours: `0 */4 * * * ?`
- Every day at 2 AM: `0 0 2 * * ?`
- Every 15 minutes: `0 */15 * * * ?`

### Option B: Delta Live Tables (For Streaming)

If you need near-real-time replication, use Delta Live Tables:

```python
import dlt

@dlt.table(
    name="bronze_sku_data",
    comment="Bronze layer - raw data from Lakebase"
)
def bronze_sku_data():
    return spark.readStream \
        .option("readChangeFeed", "true") \
        .table("range_optimizer_catalog.range_optimizer.sku_data")

@dlt.table(
    name="silver_sku_data",
    comment="Silver layer - cleaned and validated"
)
@dlt.expect_or_drop("valid_sell_id", "SELL_ID IS NOT NULL")
@dlt.expect_or_drop("positive_price", "SELLING_PRICE > 0")
def silver_sku_data():
    return dlt.read_stream("bronze_sku_data")
```

## Step 4: Query and Use Delta Tables

### Query the Delta Table

```sql
-- Query the Delta table
SELECT * FROM main.range_optimizer.delta_sku_data;

-- Join with other Unity Catalog tables
SELECT 
    d.*,
    f.PRODUCT_NAME,
    f.CATEGORY_NAME
FROM main.range_optimizer.delta_sku_data d
JOIN main.stock_optimization.product_features f
    ON d.SELL_ID = f.SELL_ID;
```

### Use in Python/Spark

```python
# Read Delta table
df = spark.table("main.range_optimizer.delta_sku_data")

# Convert to Pandas for Dash app
import pandas as pd
pandas_df = df.toPandas()
```

### Access from Dash App

```python
from databricks import sql
import os

# Connect to Databricks SQL warehouse
with sql.connect(
    server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
    http_path=os.getenv("DATABRICKS_HTTP_PATH"),
    access_token=os.getenv("DATABRICKS_TOKEN")
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM main.range_optimizer.delta_sku_data")
        df = cursor.fetchall_arrow().to_pandas()
```

## Important Considerations

### Read-Only Source Catalog

⚠️ The registered Lakebase catalog is **read-only** through Unity Catalog. You cannot:
- `INSERT`, `UPDATE`, or `DELETE` data through Unity Catalog
- Modify schema through Unity Catalog

To write data, use:
- Direct Lakebase connection (PostgreSQL client)
- Lakebase SQL Editor
- Your Dash app's direct database connection

### Data Freshness

- **Lakebase → UC Catalog**: Metadata is cached; may need refresh for new tables/schemas
- **UC Catalog → Delta**: Data is as fresh as your replication schedule
- For real-time needs, consider more frequent replication or streaming

### Performance

- **Lakebase queries**: Good for small-to-medium datasets
- **Delta queries**: Optimized for large-scale analytics
- **Best practice**: Use Lakebase for OLTP, Delta for analytics

### Cost Optimization

- Schedule replication during off-peak hours
- Use incremental sync when possible (more efficient)
- Consider cluster autoscaling for scheduled jobs
- Use Serverless for on-demand workloads

## Troubleshooting

### Catalog Not Found

```
Error: Catalog 'range_optimizer_catalog' not found
```

**Solution**: Register the Lakebase database first (see Step 1)

### Table Not Visible

```
Error: Table 'range_optimizer_catalog.range_optimizer.sku_data' not found
```

**Solution**: 
1. Check if the table exists in Lakebase
2. Refresh the catalog metadata in Catalog Explorer
3. Verify schema name spelling

### Permission Denied

```
Error: User does not have SELECT privilege on table
```

**Solution**: Grant Unity Catalog permissions:
```sql
GRANT USE CATALOG ON CATALOG range_optimizer_catalog TO `user@domain.com`;
GRANT USE SCHEMA ON SCHEMA range_optimizer_catalog.range_optimizer TO `user@domain.com`;
GRANT SELECT ON TABLE range_optimizer_catalog.range_optimizer.sku_data TO `user@domain.com`;
```

### Slow Replication

**Solutions**:
- Use incremental sync instead of full refresh
- Optimize Delta table: `OPTIMIZE main.range_optimizer.delta_sku_data`
- Add Z-ORDER: `OPTIMIZE main.range_optimizer.delta_sku_data ZORDER BY (SELL_ID)`
- Use larger cluster for replication job

## Documentation References

- [Register Lakebase in Unity Catalog](https://docs.databricks.com/aws/en/oltp/projects/register-uc)
- [Query Federated Sources](https://docs.databricks.com/aws/en/query-federation/database-federation)
- [Delta Lake Documentation](https://docs.databricks.com/aws/en/delta/)
- [Delta Change Data Feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)
- [Databricks Workflows](https://docs.databricks.com/aws/en/workflows/)

## Next Steps

1. ✅ **Run the notebook**: `notebooks/04_replicate_lakebase_to_delta.py`
2. ✅ **Schedule the workflow**: Set up automated replication
3. ✅ **Monitor replication**: Check job runs and data freshness
4. ✅ **Optimize queries**: Create views and optimize Delta tables
5. ✅ **Update your app**: Point analytics queries to Delta tables
