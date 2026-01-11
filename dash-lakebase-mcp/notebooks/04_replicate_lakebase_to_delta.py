# Databricks notebook source
# MAGIC %md
# MAGIC # 🔄 Replicate Lakebase to Delta - Official Method
# MAGIC 
# MAGIC This notebook demonstrates the **official Databricks approach** to replicate data from Lakebase (PostgreSQL) to Delta Lake.
# MAGIC 
# MAGIC ## Architecture
# MAGIC ```
# MAGIC Step 1: Register Lakebase in Unity Catalog (one-time setup)
# MAGIC ┌──────────────────────┐
# MAGIC │ Lakebase Postgres    │ ──register──> 🔗 Read-Only UC Catalog
# MAGIC │  - daveok instance   │              (range_optimizer_catalog)
# MAGIC │  - range_optimizer   │
# MAGIC │    └── sku_data      │
# MAGIC └──────────────────────┘
# MAGIC 
# MAGIC Step 2: Replicate to Delta (this notebook)
# MAGIC 🔗 range_optimizer_catalog.range_optimizer.sku_data (read-only)
# MAGIC                    ↓ CTAS / INSERT
# MAGIC 📊 main.range_optimizer.delta_sku_data (Delta table)
# MAGIC ```
# MAGIC 
# MAGIC ## Features
# MAGIC - ✅ Uses official Databricks Lakebase + Unity Catalog integration
# MAGIC - ✅ Full refresh or incremental (MERGE) modes
# MAGIC - ✅ Automatic schema detection
# MAGIC - ✅ Data quality checks
# MAGIC - ✅ Can be scheduled as Databricks Workflow
# MAGIC 
# MAGIC ## Prerequisites
# MAGIC 1. Lakebase database must be registered in Unity Catalog (see Step 1 below)
# MAGIC 2. Serverless SQL warehouse or cluster with Unity Catalog enabled

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
# Source: Registered Lakebase catalog in Unity Catalog (read-only)
SOURCE_CATALOG = "range_optimizer_catalog"  # The registered Lakebase catalog
SOURCE_SCHEMA = "range_optimizer"
SOURCE_TABLE = "sku_data"
SOURCE_FULL_PATH = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{SOURCE_TABLE}"

# Target: Delta Lake in Unity Catalog
TARGET_CATALOG = "smarter_forecasting"  # Or your preferred catalog
TARGET_SCHEMA = "range_optimizer"
TARGET_TABLE = "delta_sku_data"
TARGET_FULL_PATH = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{TARGET_TABLE}"

# Replication Settings
REPLICATION_MODE = "full"  # "full" or "incremental"
PRIMARY_KEY = "SELL_ID"  # Primary key for MERGE operations
INCREMENTAL_COLUMN = "UPDATED_AT"  # Timestamp column for incremental sync

print(f"📥 Source (Lakebase UC Catalog): {SOURCE_FULL_PATH}")
print(f"📤 Target (Delta Lake): {TARGET_FULL_PATH}")
print(f"🔄 Mode: {REPLICATION_MODE.upper()}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Step 1: Register Lakebase Database (One-Time Setup)
# MAGIC 
# MAGIC **If you haven't already registered your Lakebase database in Unity Catalog**, follow these steps:
# MAGIC 
# MAGIC ### Option A: Using the UI (Recommended)
# MAGIC 1. Navigate to **Catalog Explorer** in Databricks
# MAGIC 2. Click the **+** icon → **Create a catalog**
# MAGIC 3. Enter catalog name: `range_optimizer_catalog`
# MAGIC 4. Select **Lakebase Postgres** as catalog type
# MAGIC 5. Choose **Autoscaling** option
# MAGIC 6. Select:
# MAGIC    - Project: (your Lakebase project)
# MAGIC    - Branch: `main` (or your branch)
# MAGIC    - Postgres database: `databricks_postgres`
# MAGIC 7. Click **Create**
# MAGIC 
# MAGIC ### Option B: Using Python SDK
# MAGIC ```python
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks.sdk.service.catalog import CreateCatalog, CatalogType
# MAGIC 
# MAGIC w = WorkspaceClient()
# MAGIC 
# MAGIC # Register Lakebase database as UC catalog
# MAGIC catalog = w.catalogs.create(
# MAGIC     name="range_optimizer_catalog",
# MAGIC     comment="Read-only catalog for Lakebase daveok instance",
# MAGIC     connection_name="daveok",  # Your Lakebase instance name
# MAGIC     options={
# MAGIC         "database": "databricks_postgres"
# MAGIC     }
# MAGIC )
# MAGIC print(f"✅ Registered catalog: {catalog.name}")
# MAGIC ```
# MAGIC 
# MAGIC ### Verify Registration
# MAGIC Run the cell below to verify the catalog is registered:

# COMMAND ----------

# DBTITLE 1,Verify Lakebase Catalog Registration
# Check if source catalog exists
try:
    catalogs = [cat.name for cat in spark.catalog.listCatalogs()]
    
    if SOURCE_CATALOG in catalogs:
        print(f"✅ Catalog '{SOURCE_CATALOG}' is registered")
        
        # Show available schemas
        spark.catalog.setCurrentCatalog(SOURCE_CATALOG)
        schemas = [s.name for s in spark.catalog.listDatabases()]
        print(f"   Schemas: {', '.join(schemas)}")
        
        # Show tables in the schema
        if SOURCE_SCHEMA in schemas:
            tables = [t.name for t in spark.catalog.listTables(SOURCE_SCHEMA)]
            print(f"   Tables in '{SOURCE_SCHEMA}': {', '.join(tables)}")
            
            if SOURCE_TABLE in tables:
                print(f"   ✅ Source table '{SOURCE_TABLE}' found!")
            else:
                print(f"   ⚠️ Table '{SOURCE_TABLE}' not found in schema")
        else:
            print(f"   ⚠️ Schema '{SOURCE_SCHEMA}' not found")
    else:
        print(f"❌ Catalog '{SOURCE_CATALOG}' is NOT registered")
        print(f"   Available catalogs: {', '.join(catalogs)}")
        print(f"\n   👉 Please register your Lakebase database first (see Step 1 above)")
        
except Exception as e:
    print(f"❌ Error checking catalog: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Step 2: Preview Source Data from Lakebase

# COMMAND ----------

# DBTITLE 1,Query Lakebase via Unity Catalog
# Query the registered Lakebase catalog (read-only)
print(f"📋 Querying source table: {SOURCE_FULL_PATH}\n")

source_df = spark.sql(f"""
    SELECT * 
    FROM {SOURCE_FULL_PATH}
    LIMIT 10
""")

print(f"Schema:")
source_df.printSchema()

print(f"\nSample data:")
display(source_df)

# COMMAND ----------

# DBTITLE 1,Get Row Count
row_count = spark.sql(f"SELECT COUNT(*) as count FROM {SOURCE_FULL_PATH}").first()['count']
print(f"📊 Total rows in source table: {row_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔍 Step 3: Data Quality Checks

# COMMAND ----------

# DBTITLE 1,Validate Data Quality
print("=" * 60)
print("📊 DATA QUALITY CHECKS")
print("=" * 60)

# Check for null primary keys
null_pks = spark.sql(f"""
    SELECT COUNT(*) as count 
    FROM {SOURCE_FULL_PATH} 
    WHERE {PRIMARY_KEY} IS NULL
""").first()['count']

# Check for duplicate primary keys
duplicate_pks = spark.sql(f"""
    SELECT COUNT(*) as count
    FROM (
        SELECT {PRIMARY_KEY}, COUNT(*) as cnt
        FROM {SOURCE_FULL_PATH}
        GROUP BY {PRIMARY_KEY}
        HAVING cnt > 1
    )
""").first()['count']

# Get schema column count
schema = spark.table(SOURCE_FULL_PATH).schema
column_count = len(schema)

print(f"Total Rows: {row_count:,}")
print(f"Null Primary Keys: {null_pks}")
print(f"Duplicate Primary Keys: {duplicate_pks}")
print(f"Schema Columns: {column_count}")

if null_pks > 0:
    print(f"\n⚠️ WARNING: Found {null_pks} rows with null primary keys")
if duplicate_pks > 0:
    print(f"⚠️ WARNING: Found {duplicate_pks} duplicate primary keys")
if null_pks == 0 and duplicate_pks == 0:
    print("\n✅ All data quality checks passed!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💾 Step 4: Replicate to Delta Lake

# COMMAND ----------

# DBTITLE 1,Create Target Schema
# Ensure target catalog and schema exist
spark.sql(f"CREATE CATALOG IF NOT EXISTS {TARGET_CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_CATALOG}.{TARGET_SCHEMA}")
print(f"✅ Target schema ready: {TARGET_CATALOG}.{TARGET_SCHEMA}")

# COMMAND ----------

# DBTITLE 1,Full Refresh - Overwrite Entire Table
if REPLICATION_MODE == "full":
    print(f"🔄 Performing FULL REFRESH")
    print(f"   Source: {SOURCE_FULL_PATH}")
    print(f"   Target: {TARGET_FULL_PATH}")
    
    # Option 1: Using CTAS (Create Table As Select)
    # This is the cleanest approach for full refresh
    spark.sql(f"""
        CREATE OR REPLACE TABLE {TARGET_FULL_PATH}
        USING DELTA
        TBLPROPERTIES (
            'delta.enableChangeDataFeed' = 'true',
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true',
            'description' = 'Replicated from Lakebase {SOURCE_FULL_PATH}'
        )
        AS SELECT 
            *,
            current_timestamp() as _replicated_at
        FROM {SOURCE_FULL_PATH}
    """)
    
    # Get final count
    target_count = spark.table(TARGET_FULL_PATH).count()
    print(f"\n✅ Full refresh completed!")
    print(f"   📊 Replicated {target_count:,} rows")

# COMMAND ----------

# DBTITLE 1,Incremental - MERGE Changed Rows
if REPLICATION_MODE == "incremental":
    print(f"🔄 Performing INCREMENTAL SYNC")
    print(f"   Source: {SOURCE_FULL_PATH}")
    print(f"   Target: {TARGET_FULL_PATH}")
    
    # Check if target table exists
    table_exists = spark.catalog.tableExists(TARGET_FULL_PATH)
    
    if not table_exists:
        print(f"   ℹ️ Target table doesn't exist - performing initial load")
        
        # Initial load - create table with all data
        spark.sql(f"""
            CREATE TABLE {TARGET_FULL_PATH}
            USING DELTA
            TBLPROPERTIES (
                'delta.enableChangeDataFeed' = 'true',
                'delta.autoOptimize.optimizeWrite' = 'true',
                'delta.autoOptimize.autoCompact' = 'true',
                'description' = 'Replicated from Lakebase {SOURCE_FULL_PATH}'
            )
            AS SELECT 
                *,
                current_timestamp() as _replicated_at
            FROM {SOURCE_FULL_PATH}
        """)
        
        target_count = spark.table(TARGET_FULL_PATH).count()
        print(f"   ✅ Initial load completed: {target_count:,} rows")
        
    else:
        # Get last sync timestamp
        last_sync = spark.sql(f"""
            SELECT MAX({INCREMENTAL_COLUMN}) as last_sync
            FROM {TARGET_FULL_PATH}
        """).first()['last_sync']
        
        if last_sync:
            print(f"   📅 Last sync: {last_sync}")
            
            # Get changed rows since last sync
            changed_count = spark.sql(f"""
                SELECT COUNT(*) as count
                FROM {SOURCE_FULL_PATH}
                WHERE {INCREMENTAL_COLUMN} > '{last_sync}'
            """).first()['count']
            
            print(f"   📊 Changed rows: {changed_count:,}")
            
            if changed_count > 0:
                # MERGE changed rows
                spark.sql(f"""
                    MERGE INTO {TARGET_FULL_PATH} AS target
                    USING (
                        SELECT 
                            *,
                            current_timestamp() as _replicated_at
                        FROM {SOURCE_FULL_PATH}
                        WHERE {INCREMENTAL_COLUMN} > '{last_sync}'
                    ) AS source
                    ON target.{PRIMARY_KEY} = source.{PRIMARY_KEY}
                    WHEN MATCHED THEN UPDATE SET *
                    WHEN NOT MATCHED THEN INSERT *
                """)
                
                print(f"   ✅ Merge completed: {changed_count:,} rows updated/inserted")
            else:
                print(f"   ℹ️ No new changes to sync")
        else:
            print(f"   ⚠️ Could not determine last sync timestamp")
    
    # Show final count
    target_count = spark.table(TARGET_FULL_PATH).count()
    print(f"\n📊 Target table now has {target_count:,} total rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Step 5: Verify Replication

# COMMAND ----------

# DBTITLE 1,Compare Source and Target
print("=" * 60)
print("📊 REPLICATION SUMMARY")
print("=" * 60)

source_count = spark.table(SOURCE_FULL_PATH).count()
target_count = spark.table(TARGET_FULL_PATH).count()

print(f"\n📥 Source (Lakebase): {source_count:,} rows")
print(f"📤 Target (Delta): {target_count:,} rows")
print(f"🔄 Mode: {REPLICATION_MODE.upper()}")

if REPLICATION_MODE == "full":
    if source_count == target_count:
        print("\n✅ SUCCESS: Row counts match!")
    else:
        print(f"\n⚠️ WARNING: Row count mismatch")
        print(f"   Difference: {abs(source_count - target_count):,} rows")
else:
    print(f"\n✅ Incremental sync completed")

# COMMAND ----------

# DBTITLE 1,Preview Target Delta Table
print(f"\n📋 Sample data from target Delta table:\n")
display(spark.table(TARGET_FULL_PATH).limit(10))

# COMMAND ----------

# DBTITLE 1,Show Table Details
table_details = spark.sql(f"DESCRIBE DETAIL {TARGET_FULL_PATH}").first()

print("=" * 60)
print(f"📋 DELTA TABLE DETAILS")
print("=" * 60)
print(f"Name: {TARGET_FULL_PATH}")
print(f"Location: {table_details['location']}")
print(f"Format: {table_details['format']}")
print(f"Number of Files: {table_details['numFiles']}")
print(f"Size: {table_details['sizeInBytes'] / (1024**2):.2f} MB")
print(f"Created: {table_details['createdAt']}")
print(f"Last Modified: {table_details['lastModified']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Step 6: Optimize Delta Table

# COMMAND ----------

# DBTITLE 1,Optimize and Z-Order
# Optimize files for better query performance
print("🔧 Optimizing Delta table...")
spark.sql(f"OPTIMIZE {TARGET_FULL_PATH}")
print("✅ Table optimized")

# Optional: Z-ORDER by commonly filtered columns
# Uncomment if you have columns that are frequently used in WHERE clauses
# spark.sql(f"OPTIMIZE {TARGET_FULL_PATH} ZORDER BY (CATEGORY_NAME, {PRIMARY_KEY})")
# print("✅ Z-ORDER applied")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Step 7: Query Both Tables (Federated Query)
# MAGIC 
# MAGIC Demonstrate querying both Lakebase (via registered catalog) and Delta table together:

# COMMAND ----------

# DBTITLE 1,Federated Query Example
print("🔗 Federated Query: Join Lakebase and Delta tables\n")

# Example: Compare data between source and target
comparison = spark.sql(f"""
    SELECT 
        'Source (Lakebase)' as source,
        COUNT(*) as total_rows,
        COUNT(DISTINCT {PRIMARY_KEY}) as unique_products,
        SUM(CAST(TOTAL_FORECAST_30D AS DOUBLE)) as total_forecast
    FROM {SOURCE_FULL_PATH}
    
    UNION ALL
    
    SELECT 
        'Target (Delta)' as source,
        COUNT(*) as total_rows,
        COUNT(DISTINCT {PRIMARY_KEY}) as unique_products,
        SUM(CAST(TOTAL_FORECAST_30D AS DOUBLE)) as total_forecast
    FROM {TARGET_FULL_PATH}
""")

display(comparison)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Replication Complete!
# MAGIC 
# MAGIC ### What You've Done
# MAGIC 1. ✅ Registered Lakebase database as Unity Catalog catalog (read-only)
# MAGIC 2. ✅ Replicated data from Lakebase to Delta Lake
# MAGIC 3. ✅ Enabled Change Data Feed for downstream consumers
# MAGIC 4. ✅ Optimized Delta table for query performance
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC #### 1. Schedule as Databricks Workflow
# MAGIC Create a workflow to run this notebook periodically:
# MAGIC 
# MAGIC ```bash
# MAGIC # Example: Run every hour
# MAGIC databricks jobs create --json '{
# MAGIC   "name": "Lakebase to Delta - SKU Data Sync",
# MAGIC   "tasks": [{
# MAGIC     "task_key": "replicate_sku_data",
# MAGIC     "notebook_task": {
# MAGIC       "notebook_path": "/Workspace/Users/your-email/notebooks/04_replicate_lakebase_to_delta",
# MAGIC       "base_parameters": {
# MAGIC         "REPLICATION_MODE": "incremental"
# MAGIC       }
# MAGIC     },
# MAGIC     "existing_cluster_id": "your-cluster-id"
# MAGIC   }],
# MAGIC   "schedule": {
# MAGIC     "quartz_cron_expression": "0 * * * * ?",
# MAGIC     "timezone_id": "UTC"
# MAGIC   }
# MAGIC }'
# MAGIC ```
# MAGIC 
# MAGIC #### 2. Use Delta Change Data Feed
# MAGIC Track changes to the Delta table:
# MAGIC 
# MAGIC ```python
# MAGIC # Read all changes since version 0
# MAGIC changes = spark.read.format("delta") \
# MAGIC     .option("readChangeFeed", "true") \
# MAGIC     .option("startingVersion", 0) \
# MAGIC     .table(TARGET_FULL_PATH)
# MAGIC 
# MAGIC display(changes)
# MAGIC ```
# MAGIC 
# MAGIC #### 3. Query Delta Table from Your App
# MAGIC ```python
# MAGIC # In your Dash app or notebook
# MAGIC df = spark.table("main.range_optimizer.delta_sku_data")
# MAGIC pandas_df = df.toPandas()
# MAGIC ```
# MAGIC 
# MAGIC #### 4. Create Views for Analytics
# MAGIC ```sql
# MAGIC CREATE OR REPLACE VIEW main.range_optimizer.sku_analytics AS
# MAGIC SELECT 
# MAGIC     CATEGORY_NAME,
# MAGIC     COUNT(*) as product_count,
# MAGIC     SUM(TOTAL_FORECAST_30D) as total_demand,
# MAGIC     AVG((SELLING_PRICE - UNIT_COST) / UNIT_COST * 100) as avg_margin_pct
# MAGIC FROM main.range_optimizer.delta_sku_data
# MAGIC GROUP BY CATEGORY_NAME;
# MAGIC ```
# MAGIC 
# MAGIC ### Documentation
# MAGIC - [Register Lakebase in Unity Catalog](https://docs.databricks.com/aws/en/oltp/projects/register-uc)
# MAGIC - [Query Federated Sources](https://docs.databricks.com/aws/en/query-federation/)
# MAGIC - [Delta Lake Change Data Feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)
