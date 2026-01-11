# Unity Catalog Integration - Lakebase Database

## Overview

This document describes the Unity Catalog integration for the Range Optimizer application's Lakebase database.

## Current Configuration

### Database Instance
- **Instance Name**: `daveok`
- **Database Name**: `databricks_postgres`
- **Schema**: `range_optimizer`

### Unity Catalog Registration
- **Catalog Name**: `range_optimizer_catalog`
- **Status**: ✅ Registered and Active
- **Owner**: david.okeeffe@databricks.com
- **Type**: Read-only Unity Catalog catalog (synced from Lakebase)

## What was Done

The Lakebase database instance has been registered as a Unity Catalog catalog using the Databricks SDK. This enables:

1. **Unity Catalog Privileges**: Manage data access using UC's fine-grained permission model
2. **Managed Data Syncing**: Automatic synchronization between Postgres and Unity Catalog
3. **Unified Governance**: Apply consistent governance policies across all data assets
4. **Discovery & Lineage**: Better data discovery and lineage tracking

## How to Access

### Via Databricks Workspace UI

1. Navigate to **Catalog** in your Databricks workspace sidebar
2. Attach a **Serverless SQL Warehouse** if prompted
3. Find and click on `range_optimizer_catalog`
4. Browse schemas and tables (they will sync automatically as you explore)

### Via SQL

```sql
-- Show all schemas in the catalog
SHOW SCHEMAS IN range_optimizer_catalog;

-- Show all tables in a schema (e.g., range_optimizer)
SHOW TABLES IN range_optimizer_catalog.range_optimizer;

-- Query data through Unity Catalog
SELECT * FROM range_optimizer_catalog.range_optimizer.your_table_name LIMIT 10;
```

### Via Python SDK

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# List schemas
schemas = w.schemas.list(catalog_name="range_optimizer_catalog")
for schema in schemas:
    print(f"Schema: {schema.name}")

# List tables in a schema
tables = w.tables.list(
    catalog_name="range_optimizer_catalog",
    schema_name="range_optimizer"
)
for table in tables:
    print(f"Table: {table.name}")
```

## Important Notes

### Read-Only Catalog
The Unity Catalog representation of your Lakebase database is **read-only**. To write data:
- Use the direct Lakebase connection (as configured in `app.yaml`)
- The MCP app has `CAN_CONNECT_AND_CREATE` permission for writes
- Changes will sync to Unity Catalog automatically

### Automatic Syncing
- Schemas and tables sync automatically when browsed in Catalog Explorer
- The UI may cache data to reduce Postgres requests
- Click the refresh button (🔄) in Catalog Explorer to trigger a full refresh

### Limitations
- Database names must only contain alphanumerical or underscore characters (no hyphens)
- Each source table can be used to create up to 20 synced tables
- Catalog names must follow Unity Catalog securable object naming constraints

## Management Scripts

### Register Database to UC
```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp
uv run python scripts/register_database_to_uc.py
```

This script:
- Registers the Lakebase database as a Unity Catalog catalog
- Handles existing catalog scenarios
- Provides status updates and next steps

### Verify UC Registration
```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp
uv run python scripts/verify_uc_catalog.py
```

This script:
- Verifies the catalog exists in Unity Catalog
- Lists available schemas and tables
- Checks the database catalog registration status
- Provides access instructions

## Permissions Management

### Grant Catalog Access to Users
```sql
-- Grant USAGE on catalog
GRANT USAGE ON CATALOG range_optimizer_catalog TO `user@example.com`;

-- Grant SELECT on all tables in a schema
GRANT SELECT ON SCHEMA range_optimizer_catalog.range_optimizer TO `user@example.com`;

-- Grant SELECT on specific table
GRANT SELECT ON TABLE range_optimizer_catalog.range_optimizer.your_table TO `user@example.com`;
```

### Grant Catalog Access to Service Principal
```sql
GRANT USAGE ON CATALOG range_optimizer_catalog TO `service-principal-uuid`;
GRANT SELECT ON SCHEMA range_optimizer_catalog.range_optimizer TO `service-principal-uuid`;
```

## Deleting the Catalog

If you need to delete the Unity Catalog registration:

⚠️ **Important**: Delete all synced tables first. It can take up to 3 days for synced tables to be cleaned up after catalog deletion, and they count toward the 20 synced tables per source table limit.

```bash
# Via CLI
databricks database delete-database-catalog range_optimizer_catalog

# Via Python SDK
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.database.delete_database_catalog(name="range_optimizer_catalog")
```

Note: Deleting the catalog does NOT delete the underlying Postgres database.

## Integration with Apps

Both apps in this project now have access to data through two paths:

### 1. Direct Lakebase Connection (for writes)
```python
# Configured in app.yaml resources
# MCP app: CAN_CONNECT_AND_CREATE
# UI app: CAN_CONNECT (read-only)
```

### 2. Unity Catalog (for reads with governance)
```python
from databricks.sdk import WorkspaceClient
from databricks.sql import connect

# Via SDK
w = WorkspaceClient()

# Via SQL connection
connection = connect(
    server_hostname="your-workspace.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/your-warehouse-id",
    access_token="your-token"
)

cursor = connection.cursor()
cursor.execute("SELECT * FROM range_optimizer_catalog.range_optimizer.products")
results = cursor.fetchall()
```

## Monitoring and Troubleshooting

### Check Catalog Status
```sql
DESCRIBE CATALOG range_optimizer_catalog;
```

### View Sync Status
Check the Catalog Explorer UI for sync status indicators on schemas and tables.

### Common Issues

**Issue**: Schemas not appearing
- **Solution**: Navigate to the catalog in Catalog Explorer to trigger initial sync

**Issue**: Tables not syncing
- **Solution**: Click the refresh button (🔄) in Catalog Explorer

**Issue**: Permission denied
- **Solution**: Ensure you have `USAGE` privilege on the catalog and `SELECT` on schemas/tables

## References

- [Databricks Lakebase Documentation](https://docs.databricks.com/aws/en/oltp/instances/register-uc?language=Python+SDK)
- [Unity Catalog Documentation](https://docs.databricks.com/unity-catalog/index.html)
- [Databricks SDK for Python](https://databricks-sdk-py.readthedocs.io/)

## Next Steps

1. ✅ Database registered to Unity Catalog
2. 📋 Browse schemas and tables in Catalog Explorer
3. 🔐 Set up appropriate permissions for users/service principals
4. 📊 Create views or materialized views in Unity Catalog for analytics
5. 🔄 Monitor sync status and data freshness
