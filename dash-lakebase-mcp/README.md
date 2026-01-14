# Excel Writeback - Dash Application

Excel-like data editing interface with writeback to Databricks Lakebase, powered by Dash.

## 🚀 Quick Start - Local Development

Start both apps with one command:

```bash
./start-all-apps.sh
```

Access:
- **MCP App**: http://localhost:7001 (proxy) or http://localhost:7000 (direct)
- **UI App**: http://localhost:7003

**Note**: Uses port range 7000-7003 to avoid conflicts with SSH port forwarding (commonly uses 9000+)

Stop all apps:
```bash
./stop-all-apps.sh
```

### Run on custom ports (example: 7000-7004) and restart

```bash
# stop any existing sessions and free ports
./stop-all-apps.sh

# start MCP on 7000/7001
./run-databricks-app-local.sh mcp_app 7000 7001 daveok

# start UI on 7002/7003, pointing at the MCP app port (7000)
MCP_SERVER_URL=http://localhost:7000 \
  ./run-databricks-app-local.sh ui_app 7002 7003 daveok

# UI available at http://localhost:7003
```

**For detailed instructions**, see:
- [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) - Complete local development guide
- [RUN_MULTIPLE_APPS.md](./RUN_MULTIPLE_APPS.md) - Running multiple apps simultaneously

## 📋 Logging & Monitoring

Monitor your apps in both local and Databricks environments:

### Local Development Logs

```bash
# Stream MCP app logs
tail -f mcp-app.log

# Stream UI app logs
tail -f ui-app.log

# Monitor both simultaneously
tail -f mcp-app.log ui-app.log

# Filter for errors
tail -f mcp-app.log | grep -E "ERROR|WARNING"
```

### Databricks Deployment Logs

```bash
# Stream MCP app logs from Databricks
databricks apps logs range-opt-mcp-daveok --follow

# Stream UI app logs from Databricks
databricks apps logs range-opt-ui-daveok --follow

# View last 100 lines
databricks apps logs range-opt-mcp-daveok --tail 100
```

### No Conflicts Between Environments

- **Local logs**: Written to `./mcp-app.log` and `./ui-app.log` (local filesystem)
- **Databricks logs**: Stored in cloud, accessed via CLI (no local files)
- Both can run simultaneously without interference

**For comprehensive logging guide**, see [LOGGING_GUIDE.md](./LOGGING_GUIDE.md)

## Architecture

This application consists of two separate components for security isolation:

### 1. **Dash UI Application** (Main App)
- Full-stack Dash application with data grid interface
- Serves at `http://localhost:7002` (app) or `http://localhost:7003` (proxy)
- REST API at `/api`
- Restricted database permissions (read/write via app logic)

### 2. **MCP Server** (AI Tooling)
- Standalone Model Context Protocol server
- Serves at `http://localhost:7000` (app) or `http://localhost:7001` (proxy)
- Elevated permissions for AI-powered operations
- Used by Claude Desktop and other MCP clients

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Databricks workspace with Lakebase instance
- `.env` file with Databricks credentials

### Installation

```bash
# Install dependencies
uv sync

# Copy .env.example to .env and configure
cp .env.example .env
```

### Development

#### Run Dash UI (Main App)
```bash
./start-ui-app.sh
# Or manually:
uv run uvicorn range_optimizer.backend.app:app --reload --port 7002
```

Access at: **http://localhost:7002** (or **http://localhost:7003** via proxy)

#### Run MCP Server (Optional - for AI features)
```bash
# Manually:
uv run uvicorn range_optimizer.backend.mcp_standalone:app --reload --port 7000
```

Access at: **http://localhost:7000/mcp** (or **http://localhost:7001/mcp** via proxy)

## Features

### Dash UI
- 📊 Excel-like data grid with AG Grid
- ✏️  Inline editing with validation
- 💾 Writeback to Databricks Lakebase
- 📈 Stock optimization recommendations
- 🎨 Modern UI with Dash Mantine Components
- 🔗 Unity Catalog integration for governed data access

### ML Model Integration (NEW!)
- 🤖 Classical ML model for stock optimization using EOQ
- 🎯 Feature Store integration with automatic feature lookup
- 📊 Unity Catalog model registration and governance
- 🚀 Model serving with real-time inference
- 📈 Complete feature-to-model lineage tracking

See [notebooks/README.md](./notebooks/README.md) and [DATABRICKS_ML_IMPLEMENTATION.md](./DATABRICKS_ML_IMPLEMENTATION.md) for details.

### MCP Server
- 🤖 AI-powered data analysis tools
- 🔍 Unity Catalog metadata exploration
- 📊 SQL query execution
- 🧠 LLM-powered insights

### Unity Catalog Integration
- ✅ Lakebase database registered as UC catalog (`range_optimizer_catalog`)
- 🔐 Fine-grained access control via Unity Catalog permissions
- 🔄 Automatic sync between Postgres and Unity Catalog
- 📋 Unified governance across all data assets

## Deployment

### Deploy to Databricks Apps

```bash
# Deploy both apps
databricks bundle deploy

# Deploy individually
databricks bundle deploy --resource apps.range_optimizer_ui
databricks bundle deploy --resource apps.range_optimizer_mcp
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

### Monitoring Deployed Apps

```bash
# Check app status
databricks apps get range-opt-mcp-daveok
databricks apps get range-opt-ui-daveok

# Stream logs in real-time
databricks apps logs range-opt-mcp-daveok --follow
databricks apps logs range-opt-ui-daveok --follow
```

See [LOGGING_GUIDE.md](LOGGING_GUIDE.md) for complete monitoring guide.

### Unity Catalog Setup

The Lakebase database is registered with Unity Catalog for governed data access:

```bash
# Register database to Unity Catalog (already completed)
uv run python scripts/register_database_to_uc.py

# Verify UC registration and explore catalog
uv run python scripts/verify_uc_catalog.py
```

See [UNITY_CATALOG_SETUP.md](UNITY_CATALOG_SETUP.md) for detailed UC configuration and usage.

### ML Model Training & Deployment

Train and deploy the stock optimization ML model:

```bash
# Run Databricks notebooks in order:
# 1. notebooks/00_create_feature_tables.py     - Create feature tables
# 2. notebooks/01_train_stock_optimizer.py     - Train with Feature Store
# 3. notebooks/02_deploy_serving_endpoint.py   - Deploy to serving endpoint

# View complete documentation
# See: notebooks/README.md
# See: DATABRICKS_ML_IMPLEMENTATION.md
```

**Key Features**:
- ✅ Feature Store integration with automatic feature lookup
- ✅ Unity Catalog model registration and governance
- ✅ Complete feature-to-model lineage tracking
- ✅ Real-time model serving with auto-scaling
- ✅ Follows official Databricks best practices

## Project Structure

```
dash-lakebase-mcp/
├── mcp_app/
│   └── range_optimizer/
│   └── backend/
│       ├── app.py              # Main Dash application
│       ├── mcp_standalone.py   # Standalone MCP server
│       ├── pages/              # Dash pages
│       ├── callbacks/          # Dash callbacks
│       ├── components/         # Dash components
│       ├── mcp/                # MCP tools
│       ├── ml/                 # ML models and optimization
│       ├── database.py         # Lakebase connection
│       └── models.py           # Data models
├── notebooks/                  # Databricks ML notebooks
│   ├── 00_create_feature_tables.py      # Feature Store setup
│   ├── 01_train_stock_optimizer.py      # Model training
│   ├── 02_deploy_serving_endpoint.py    # Model deployment
│   └── README.md                         # Complete ML documentation
├── databricks.yml              # DAB configuration
├── ui_app/                     # UI app deployment
│   └── app.yaml               # UI permissions (restricted)
├── mcp_app/                    # MCP app deployment
│   └── app.yaml               # MCP permissions (elevated)
├── mcp-app.log                 # Local MCP app logs (gitignored)
├── ui-app.log                  # Local UI app logs (gitignored)
├── DATABRICKS_ML_IMPLEMENTATION.md      # ML best practices guide
├── LOGGING_GUIDE.md            # Comprehensive logging documentation
└── scripts/                    # Utility scripts
```

## Configuration

### Environment Variables

Create a `.env` file with:

```bash
# Databricks Configuration
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your-token

# Lakebase Configuration
LAKEBASE_INSTANCE_NAME=your-instance
LAKEBASE_DATABASE=databricks_postgres
LAKEBASE_SCHEMA=range_optimizer
```

### Database Permissions

**UI App** (Restricted):
- `CAN_CONNECT` - Database access
- `CAN_USE` - SQL Warehouse access

**MCP Server** (Elevated):
- `CAN_CONNECT_AND_CREATE` - Full database access
- `CAN_USE` - SQL Warehouse access
- `CAN_QUERY` - LLM endpoint access

## Development Workflow

### Make Code Changes
1. Edit files in `src/range_optimizer/backend/`
2. Uvicorn auto-reloads on save
3. Test in browser

### Add New Dash Pages
1. Create file in `src/range_optimizer/backend/pages/`
2. Use Dash `register_page()` decorator
3. Add callbacks in `src/range_optimizer/backend/callbacks/`

### Add MCP Tools
1. Add tool functions in `src/range_optimizer/backend/mcp/tools.py`
2. Register with FastMCP decorators
3. Test with Claude Desktop

## Testing

```bash
# Run linter
uv run ruff check src/

# Type checking
uv run pyright src/
```

## Tech Stack

- **Framework**: Dash (Plotly)
- **API**: FastAPI
- **UI Components**: Dash Mantine Components, AG Grid
- **Database**: Databricks Lakebase (PostgreSQL)
- **AI**: FastMCP, Databricks LLM endpoints
- **Deployment**: Databricks Apps

## Security

- **Separation of Concerns**: UI and MCP run as separate apps
- **Principle of Least Privilege**: Different permission levels per app
- **Blast Radius Limitation**: UI vulnerabilities can't access MCP privileges
- **OAuth Authentication**: Databricks workspace authentication

## Contributing

1. Make changes in feature branch
2. Test locally with `./start-all-apps.sh`
3. Validate DAB: `databricks bundle validate`
4. Submit PR

## License

Internal Databricks Solutions Accelerator

## Support

For issues or questions, contact the Databricks Solutions Architecture team.
