# Database Connection Warning - Resolution

## Issue
When deploying the MCP app in Databricks, you saw this warning:
```
WARNING | Database connection pool not initialized - some features may not work
```

## Root Cause
The app configuration was manually setting custom `LAKEBASE_*` environment variables and trying to dynamically resolve the database host using the Databricks SDK. However, **Databricks automatically injects standard PostgreSQL environment variables** when you declare a database resource in `app.yaml`.

## What Databricks Provides Automatically

According to [Databricks documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/lakebase), when you add a database resource to your app, Databricks automatically injects these environment variables:

- **`PGHOST`** - The hostname of the database instance (e.g., `ep-abc-123.databricks.com`)
- **`PGDATABASE`** - The database name (e.g., `databricks_postgres`)
- **`PGUSER`** - The service principal's username (OAuth-based authentication)
- **`PGAPPNAME`** - The app name

These are standard PostgreSQL environment variables that libraries like `psycopg` automatically recognize.

## Changes Made

### 1. Simplified `app.yaml` Files
**Before:**
```yaml
env:
  - name: LAKEBASE_INSTANCE_NAME
    value: daveok
  - name: LAKEBASE_DATABASE
    value: databricks_postgres
  - name: LAKEBASE_SCHEMA
    value: range_optimizer
```

**After:**
```yaml
env:
  # Schema name for database tables
  # Note: Databricks automatically injects PGHOST, PGDATABASE, PGUSER
  - name: LAKEBASE_SCHEMA
    value: range_optimizer
```

We removed the redundant `LAKEBASE_INSTANCE_NAME` and `LAKEBASE_DATABASE` variables since Databricks provides `PGHOST` and `PGDATABASE` directly.

### 2. Simplified `entrypoint.sh` Files
**Before:** Complex bash script trying to resolve `PGHOST` using Python and the Databricks SDK

**After:** Simple debug output showing the injected variables:
```bash
#!/bin/bash
set -e

# Debug: Print database environment variables (Databricks injects these automatically)
echo "Database configuration:"
echo "  PGHOST: ${PGHOST:-<not set>}"
echo "  PGDATABASE: ${PGDATABASE:-<not set>}"
echo "  PGUSER: ${PGUSER:-<not set>}"
echo "  PGPORT: ${PGPORT:-5432}"
echo "  PGSSLMODE: ${PGSSLMODE:-require}"

# Run the application
exec uvicorn range_optimizer.backend.app:app --host 0.0.0.0 --port 9000
```

### 3. Enhanced Error Logging
Updated `config.py` and `database.py` to log detailed error messages when database configuration fails, making debugging easier.

## Local Development

For local development, use the **`databricks apps run-local`** command, which automatically injects the same environment variables (including `PGHOST`, `PGDATABASE`, `PGUSER`) as production:

```bash
cd mcp_app
databricks apps run-local
```

This eliminates the need to manually configure database credentials. See [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) for full details.

## How the Config Works Now

The `DatabaseConfig` class in `config.py` uses Pydantic's field aliases to map environment variables:

```python
class DatabaseConfig(BaseSettings):
    # These map to the PG* variables that Databricks injects
    pg_host: Optional[str] = Field(default=None, alias="PGHOST")
    pg_database: Optional[str] = Field(default=None, alias="PGDATABASE")
    pg_user: Optional[str] = Field(default=None, alias="PGUSER")
    
    # Custom schema name (still needed as Databricks doesn't inject this)
    schema_name: str = Field(default="range_optimizer", alias="LAKEBASE_SCHEMA")
```

The `@computed_field` properties (`host`, `database`, `user`) now:
1. First check if `PGHOST`, `PGDATABASE`, `PGUSER` are set (injected by Databricks)
2. Fall back to SDK lookups only if needed (for local development)
3. Log errors clearly if resolution fails

## Testing the Fix

After deploying with these changes, check the app logs. You should see:

```
Database configuration:
  PGHOST: ep-xyz-123.databricks.com
  PGDATABASE: databricks_postgres
  PGUSER: some-service-principal-id
  PGPORT: 5432
  PGSSLMODE: require

...

Initializing Databricks Lakebase connection pool
  Resolved host: ep-xyz-123.databricks.com
  Resolved database: databricks_postgres
  Resolved user: some-service-principal-id
  Resolved instance_name: daveok
Connection pool initialized with OAuth authentication
```

If you still see the warning, the logs will now show exactly which variable is missing.

## Why This Works

- **Less Code**: No custom resolution logic needed
- **Standard Practice**: Uses PostgreSQL environment variables that are industry-standard
- **Better Security**: Databricks manages credential injection securely
- **Local Dev Compatible**: The fallback SDK logic still works for local development
- **Clear Errors**: Enhanced logging shows exactly what's missing

## References

- [Add a Lakebase resource to a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/lakebase)
- [Define environment variables in a Databricks app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/environment-variables)
