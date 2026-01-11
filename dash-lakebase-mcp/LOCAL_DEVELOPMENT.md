# Local Development Guide

## Running Databricks Apps Locally

Databricks provides the **`databricks apps run-local`** command that allows you to run your app locally with the **same environment variables that are injected in production**, including database credentials.

## Quick Start

### Using `databricks apps run-local` (with helper scripts)

⚠️ **Important Discovery**: `databricks apps run-local` does **NOT** automatically inject database environment variables from resource declarations. You must provide them manually.

We've created helper scripts that automatically fetch credentials and start the apps:

```bash
# Start MCP app (runs on ports 9000/9001)
cd mcp_app
./run-local.sh

# In a different terminal, start UI app (would run on ports 8002/8003)
cd ui_app
./run-local.sh
```

These scripts automatically:
- Fetch database hostname from Databricks
- Get your current user email
- Pass all required environment variables to `databricks apps run-local`

**What this does:**
- ✅ Reads your `app.yaml` configuration
- ✅ Sets up authentication using your personal Databricks credentials
- ✅ Runs a lightweight proxy to simulate Databricks HTTP headers
- ✅ Connects to live Databricks resources (databases, SQL warehouses, serving endpoints)
- ⚠️ **Does NOT automatically inject database credentials from resource declarations** - you must provide them via `--env` flags

**Requirements:**
- Databricks CLI installed and configured (version 0.205+)
- Authenticated with your Databricks workspace

### Command Options

```bash
# Run on a custom port
databricks apps run-local --app-port 9000 --port 9001

# Use a different app.yaml file
databricks apps run-local --entry-point my-app.yaml

# Set additional environment variables
databricks apps run-local --env "LOG_LEVEL=debug" --env "DEBUG=true"

# Prepare the environment (install dependencies with uv)
databricks apps run-local --prepare-environment

# Enable debug mode
databricks apps run-local --debug --debug-port 5678
```

## Environment Variables Injected by `run-local`

When you use `databricks apps run-local`, it automatically injects the same environment variables as production:

### Database Resources (from `app.yaml`)

If your `app.yaml` declares a database resource:

```yaml
resources:
  - name: postgres-database
    database:
      database_name: databricks_postgres
      instance_name: daveok
      permission: CAN_CONNECT_AND_CREATE
```

**These are automatically injected:**

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `PGHOST` | Database hostname | `ep-abc-123.databricks.com` |
| `PGDATABASE` | Database name | `databricks_postgres` |
| `PGUSER` | Your Databricks email | `your.email@company.com` |
| `PGAPPNAME` | App name | `range-opt-mcp-daveok` |
| `PGPORT` | PostgreSQL port | `5432` |
| `PGSSLMODE` | SSL mode | `require` |

### Custom Environment Variables (from `app.yaml`)

Variables defined in the `env` section of your `app.yaml` are also set:

```yaml
env:
  - name: LAKEBASE_SCHEMA
    value: range_optimizer
```

## How Database Authentication Works Locally

### Production (Databricks Apps)
- Uses **Service Principal** credentials
- OAuth tokens generated automatically
- Injected as `PGUSER` and used with `RotatingTokenConnection`

### Local Development (`databricks apps run-local`)
- Uses **your personal Databricks credentials**
- OAuth tokens generated using your workspace authentication
- Same `PGUSER` (your email) and token mechanism
- **No code changes needed** - the `RotatingTokenConnection` class works identically

## Alternative: Manual Local Development

If you can't use `databricks apps run-local`, you can set environment variables manually:

### Step 1: Get Database Connection Details

1. Go to **Lakebase UI** in your Databricks workspace
2. Select your database instance (e.g., `daveok`)
3. Click **Connect**
4. Select **OAuth authentication**
5. Copy the connection details

### Step 2: Set Environment Variables

Create a `.env` file (gitignored):

```bash
# Database connection
PGHOST=ep-abc-123.databricks.com
PGDATABASE=databricks_postgres
PGUSER=your.email@company.com
PGPASSWORD=<paste-oauth-token-here>  # Expires after 24 hours
PGPORT=5432
PGSSLMODE=require

# Application settings
LAKEBASE_SCHEMA=range_optimizer

# Databricks SDK authentication
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
```

**Note:** OAuth tokens expire after 24 hours (connection idle timeout), so you'll need to refresh them regularly.

### Step 3: Run Your App

```bash
# Load environment variables and run
cd mcp_app
source .env  # or use python-dotenv
uvicorn range_optimizer.backend.mcp_standalone:app --host 0.0.0.0 --port 9000
```

## Configuration Design

Our app configuration is designed to work **seamlessly in both environments**:

### Production (Databricks Apps)
```python
# DatabaseConfig reads from environment variables
pg_host = os.getenv("PGHOST")  # ✅ Injected by Databricks
pg_database = os.getenv("PGDATABASE")  # ✅ Injected by Databricks
pg_user = os.getenv("PGUSER")  # ✅ Injected by Databricks
```

### Local Development with `run-local`
```python
# Same code - variables injected by databricks apps run-local
pg_host = os.getenv("PGHOST")  # ✅ Injected by run-local command
pg_database = os.getenv("PGDATABASE")  # ✅ Injected by run-local command
pg_user = os.getenv("PGUSER")  # ✅ Injected by run-local command
```

### Local Development without `run-local`
```python
# Same code - variables read from .env file
pg_host = os.getenv("PGHOST")  # ✅ From .env file
pg_database = os.getenv("PGDATABASE")  # ✅ From .env file
pg_user = os.getenv("PGUSER")  # ✅ From .env file
```

**The same code works everywhere!** 🎉

## Debugging

### Check What Environment Variables Are Set

Add this to your `entrypoint.sh`:

```bash
echo "Database configuration:"
echo "  PGHOST: ${PGHOST:-<not set>}"
echo "  PGDATABASE: ${PGDATABASE:-<not set>}"
echo "  PGUSER: ${PGUSER:-<not set>}"
```

### Common Issues

#### 1. Database Connection Fails Locally

**Symptom:** `Database connection pool not initialized - some features may not work`

**Solution:**
- If using `run-local`: Check that you have the database resource in `app.yaml`
- If manual setup: Verify `.env` file exists and has correct values
- Check OAuth token hasn't expired (24-hour idle timeout)
- Ensure you have network access to the Databricks database endpoint

#### 2. `databricks apps run-local` Not Found

**Solution:**
```bash
# Check CLI version (needs 0.205+)
databricks version

# Update CLI if needed
curl -fsSL https://raw.githubusercontent.com/databricks/cli/main/install.sh | sh
```

#### 3. Permission Denied to Database

**Solution:**
- Check that your user has been granted access to the database instance
- Verify permissions in Lakebase UI: Your instance → Manage roles
- Ensure you're using OAuth authentication (recommended)

## Comparing Development Methods

| Feature | `run-local` with helper script | `run-local` manual | Manual Setup | Production |
|---------|-------------------------------|-------------------|--------------|-----------|
| Database Credentials | ✅ Auto-fetched | ⚠️ Manual --env flags | ⚠️ Manual .env | ✅ Auto-injected |
| Token Rotation | ✅ Via Databricks SDK | ✅ Via Databricks SDK | ❌ Manual refresh | ✅ Handled automatically |
| Setup Complexity | 🟢 Easy (one command) | 🟡 Medium | 🟡 Medium | 🟢 Easy |
| Code Changes | ✅ None needed | ✅ None needed | ✅ None needed | ✅ None needed |
| Proxy & Headers | ✅ Included | ✅ Included | ❌ Not available | ✅ Native |

## Recommended Workflow

### 1. Initial Setup
```bash
# Install/update Databricks CLI
curl -fsSL https://raw.githubusercontent.com/databricks/cli/main/install.sh | sh

# Authenticate
databricks auth login --host https://your-workspace.cloud.databricks.com
```

### 2. Development Loop
```bash
# Edit code locally in your IDE
cd mcp_app

# Run locally with full environment injection
databricks apps run-local --prepare-environment

# Test in browser
open http://localhost:9001
```

### 3. Deploy
```bash
# Deploy to Databricks
databricks bundle deploy

# Check logs
databricks apps logs range-opt-mcp-daveok --follow
```

## References

- [Databricks Apps CLI Commands](https://docs.databricks.com/aws/en/dev-tools/cli/reference/apps-commands)
- [Databricks Apps Development Guide](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-development)
- [Lakebase Connection Guide](https://docs.databricks.com/aws/en/oltp/projects/connect-overview)
- [Databricks Community: Setting Up Development Environment](https://community.databricks.com/t5/technical-blog/setting-up-your-development-environment-for-databricks-apps/ba-p/122111)
