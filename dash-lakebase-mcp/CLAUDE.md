# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Range Optimizer is a dual-application system for stock optimization built on Databricks infrastructure:
- **UI App**: Dash-based web interface for data editing and visualization
- **MCP App**: Model Context Protocol server with elevated permissions for AI-powered operations

The system uses Databricks Lakebase (PostgreSQL) for data storage with Unity Catalog integration, and includes ML model training/serving capabilities using Feature Store.

## Development Commands

### Starting Applications

```bash
# Start both apps (recommended)
./start-all-apps.sh

# Start individual apps with custom ports (using 7000-7003 to avoid SSH conflicts)
./run-databricks-app-local.sh mcp_app 7000 7001 username
./run-databricks-app-local.sh ui_app 7002 7003 username

# Stop all apps
./stop-all-apps.sh
```

**Default ports:**
- MCP App: http://localhost:9001
- UI App: http://localhost:8003

**Note**: UI app connects to MCP app via `MCP_SERVER_URL` environment variable.

### Testing

```bash
# Run all validation tests
uv run python test_validation.py

# Run MCP API tests (requires MCP server running at localhost:7000)
uv run python test_mcp_api.py

# Run specific test file
uv run pytest mcp_app/scripts/test_model.py

# Run specific test function with verbose output
uv run pytest mcp_app/scripts/test_model.py::test_model -v -s
```

### Log Monitoring

```bash
# Stream local logs
tail -f mcp-app.log ui-app.log

# Filter for errors/warnings
tail -f mcp-app.log | grep -E "ERROR|WARNING"

# Stream Databricks deployment logs
databricks apps logs range-opt-mcp-daveok --follow
databricks apps logs range-opt-ui-daveok --follow
```

### Deployment

```bash
# Deploy both apps to Databricks
databricks bundle deploy

# Deploy individually
databricks bundle deploy --resource apps.range_optimizer_ui
databricks bundle deploy --resource apps.range_optimizer_mcp

# Validate DAB configuration
databricks bundle validate
```

### Unity Catalog and ML Model

```bash
# Verify Unity Catalog registration
uv run python scripts/verify_uc_catalog.py

# Register Lakebase database to Unity Catalog
uv run python scripts/register_database_to_uc.py

# ML Model Training (run Databricks notebooks in order):
# 1. notebooks/00_create_feature_tables.py      - Create feature tables
# 2. notebooks/01_train_stock_optimizer.py      - Train with Feature Store
# 3. notebooks/02_deploy_serving_endpoint.py    - Deploy to serving endpoint
```

## Architecture

### Dual-Application Design

**Security Isolation**: Two separate apps with different permission levels:

1. **MCP App** (`mcp_app/`)
   - Elevated permissions: `CAN_CONNECT_AND_CREATE`, `CAN_QUERY` (LLM endpoints)
   - Serves at `/api` endpoint
   - Contains ML optimization logic and MCP tools
   - Entry point: `mcp_app/range_optimizer/backend/app.py`

2. **UI App** (`ui_app/`)
   - Restricted permissions: `CAN_CONNECT`, `CAN_USE`
   - Serves Dash UI at `/` and API at `/api`
   - Communicates with MCP app via REST
   - Entry point: `ui_app/range_optimizer/backend/app.py`

### Key Architectural Patterns

**Database Connection**:
- Uses `psycopg` (PostgreSQL adapter) with connection pooling
- OAuth token rotation via `RotatingTokenConnection` class
- All queries use parameterized statements to prevent SQL injection
- Connection pool managed in `database.py` with auto-initialization

**Configuration Management**:
- Pydantic Settings for type-safe configuration
- Supports both `PG*` (Databricks deployment) and `LAKEBASE_*` (local dev) environment variables
- Computed fields auto-populate from Databricks SDK when needed
- Configuration centralized in `config.py` modules

**Data Models (3-Model Pattern)**:
- `Entity`: Base model (database representation)
- `EntityIn`: Input model for creation/updates
- `EntityOut`: Output model for API responses
- Example: `LayoutDataBase`, `LayoutDataIn`, `LayoutDataOut`

**API Design**:
- FastAPI for backend with Dash UI overlay
- All endpoints must specify `response_model` and `operation_id`
- Proper HTTP status codes and structured error handling
- Endpoints use kebab-case (e.g., `/optimization-results`)

### Directory Structure

```
├── mcp_app/                        # MCP server application
│   ├── range_optimizer/backend/
│   │   ├── app.py                  # FastAPI app entry point
│   │   ├── mcp_standalone.py       # Standalone MCP server
│   │   ├── config.py               # Pydantic settings
│   │   ├── database.py             # PostgreSQL operations with OAuth
│   │   ├── models.py               # Pydantic models (3-model pattern)
│   │   ├── router.py               # API route definitions
│   │   ├── audit_log.py            # Audit logging for MCP operations
│   │   ├── mcp/                    # MCP protocol implementation
│   │   │   ├── server.py           # MCP server setup
│   │   │   └── tools.py            # MCP tool definitions
│   │   └── ml/                     # ML models and optimization
│   │       ├── forecast_optimizer.py    # EOQ optimization logic
│   │       ├── stock_optimizer.py       # Stock optimization model
│   │       └── mlflow_client.py         # MLflow integration
│   └── scripts/                    # Utility scripts and tests
│
├── ui_app/                         # Dash UI application
│   ├── range_optimizer/backend/
│   │   ├── app.py                  # Dash app entry point
│   │   ├── config.py               # App-specific config
│   │   ├── mcp_client.py           # MCP server REST client
│   │   ├── pages/                  # Dash pages (auto-routed)
│   │   │   ├── home.py             # Home page
│   │   │   ├── stock_optimization.py
│   │   │   └── about.py
│   │   ├── components/             # Reusable Dash components
│   │   │   ├── grid_utils.py       # AG Grid helpers
│   │   │   ├── stock_optimization.py
│   │   │   ├── ai_assistant.py     # AI chat interface
│   │   │   └── tabs.py             # Tab components
│   │   └── callbacks/              # Dash callbacks (event handlers)
│   │       ├── stock_optimization_callbacks.py
│   │       ├── ai_callbacks.py
│   │       └── input_callbacks.py
│
├── notebooks/                      # Databricks ML notebooks
│   ├── 00_create_feature_tables.py          # Feature Store setup
│   ├── 01_train_stock_optimizer.py          # Model training with features
│   ├── 02_deploy_serving_endpoint.py        # Deploy to serving
│   └── 03_analyze_optimization_results.py   # Analysis utilities
│
├── scripts/                        # Utility scripts
│   ├── register_database_to_uc.py  # UC registration
│   └── verify_uc_catalog.py        # UC verification
│
├── databricks.yml                  # Databricks Asset Bundle config
├── test_validation.py              # Validation test suite
└── test_mcp_api.py                 # MCP API integration tests
```

## ML Model Integration

The system uses **Feature Store** with **Unity Catalog** for ML-powered stock optimization:

**Feature Tables** (in Unity Catalog):
- `product_features`: Static product attributes (cost, price, category, shelf space)
- `demand_features`: Demand forecasts and volatility metrics

**Model Training Workflow**:
1. Create feature tables with `FeatureEngineeringClient`
2. Define `FeatureLookup` objects for automatic feature joining
3. Train model using `fe.create_training_set()` (not manual joins)
4. Register with `fe.log_model()` (NOT `mlflow.log_model()`) to preserve feature metadata
5. Deploy to serving endpoint with automatic feature lookup

**Critical**: Always use `fe.log_model()` for models that use Feature Store. This enables automatic feature retrieval during inference - the model only needs `SELL_ID` as input.

**Model Algorithm**: Economic Order Quantity (EOQ) with safety stock optimization
- Minimizes total inventory cost (holding + ordering costs)
- Accounts for demand variability and lead time
- Outputs: optimal order quantity, safety stock, reorder point, costs, and profitability metrics

## Important Development Guidelines

### Package Management
- **Always use `uv`** (never `pip`)
- Example: `uv run python script.py`, `uv run pytest`

### Database Operations
- Use `query_df()` for SELECT queries (returns pandas DataFrame)
- Use `query_dict_list()` for dict/JSON responses
- Use `execute_sql()` for INSERT/UPDATE/DELETE
- Use `bulk_insert()` for batch operations
- Always use parameterized queries (e.g., `query_df(sql, (param1, param2))`)

### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- API endpoints: `kebab-case`

### Error Handling
- Use structured logging with context: `logger.error("msg", extra={...})`
- Raise HTTPException with appropriate status codes
- Handle database connection errors explicitly
- Include `exc_info=True` for stack traces in logs

### Type Annotations
- Always use type hints for function parameters and return values
- Use Pydantic models for API input/output validation
- Prefer `Optional[T]` over `Union[T, None]`

### Dash UI Development
- Pages in `/pages/` become automatic routes via `register_page(__name__, path="/route")`
- Separate layout definition from callback logic
- Use dash-mantine-components (`dmc`) for UI elements
- Use dash-ag-grid for data tables with editing capabilities
- Implement callbacks in separate `/callbacks/` modules
- Use loading states and error boundaries

### MCP Server Development
- Implement tools in `/mcp/tools.py` following MCP protocol
- Include audit logging for all AI operations (use `audit_log.py`)
- Maintain security isolation - MCP has elevated permissions
- MCP tools accessed via REST by UI app through `mcp_client.py`

## Unity Catalog Integration

The Lakebase PostgreSQL database is registered as Unity Catalog catalog `range_optimizer_catalog`:
- Provides governed data access with fine-grained permissions
- Enables feature-to-model lineage tracking
- Automatic sync between Postgres tables and UC tables
- Use `verify_uc_catalog.py` to explore catalog structure

## Environment Variables

Required in `.env` file:

```bash
# Databricks Configuration
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your-token

# Lakebase Configuration (local development)
LAKEBASE_INSTANCE_NAME=your-instance
LAKEBASE_DATABASE=databricks_postgres
LAKEBASE_SCHEMA=range_optimizer

# OR use standard PostgreSQL variables (Databricks deployment)
PGHOST=instance.region.azure.databricks.com
PGPORT=5432
PGDATABASE=databricks_postgres
PGUSER=your.email@company.com

# MCP Server URL (for UI app) - use port 7000 (app port) for reliability
MCP_SERVER_URL=http://localhost:7000
```

## Security Considerations

- **Principle of Least Privilege**: UI app has restricted permissions, MCP has elevated
- **Blast Radius Limitation**: UI vulnerabilities cannot access MCP privileges
- **OAuth Authentication**: All database access uses rotating OAuth tokens
- **SQL Injection Prevention**: All queries use parameterized statements
- **Audit Logging**: All MCP operations logged to `app_audit_log` table

## Tech Stack

- **Framework**: Dash (Plotly) + FastAPI
- **Database**: Databricks Lakebase (PostgreSQL) with `psycopg` adapter
- **UI Components**: Dash Mantine Components, dash-ag-grid
- **ML/AI**: MLflow, Databricks Feature Store, FastMCP
- **Deployment**: Databricks Apps with Databricks Asset Bundles (DAB)
- **Package Manager**: `uv`
- **Python Version**: 3.11+

## Common Pitfalls

1. **Don't bypass Feature Store**: Use `fe.log_model()` not `mlflow.log_model()` for feature-integrated models
2. **Don't use pip**: Always use `uv` for package management
3. **Don't hardcode SQL table names**: Use `db_config.get_full_table_name()` or property shortcuts
4. **Don't forget schema prefix**: Use `{schema}.{table}` format or config helper methods
5. **Don't skip type annotations**: All functions should have proper type hints
6. **Don't restart dev servers unnecessarily**: Uvicorn auto-reloads on file changes
7. **Don't use `git commit -i` or other interactive git commands**: Not supported in non-interactive environments
