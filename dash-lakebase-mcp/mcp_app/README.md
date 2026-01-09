# Excel Writeback - Dash Application

Excel-like data editing interface with writeback to Databricks Lakebase, powered by Dash.

## Architecture

This application consists of two separate components for security isolation:

### 1. **Dash UI Application** (Main App)
- Full-stack Dash application with data grid interface
- Serves at `http://localhost:8000`
- REST API at `/api`
- Restricted database permissions (read/write via app logic)

### 2. **MCP Server** (AI Tooling)
- Standalone Model Context Protocol server
- Serves at `http://localhost:8001`
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
./run_dev.sh
# Or manually:
uv run uvicorn excel_writeback.backend.app:app --reload --port 8000
```

Access at: **http://localhost:8000**

#### Run MCP Server (Optional - for AI features)
```bash
./run_mcp.sh
# Or manually:
uv run uvicorn excel_writeback.backend.mcp_standalone:app --reload --port 8001
```

Access at: **http://localhost:8001/mcp**

## Features

### Dash UI
- 📊 Excel-like data grid with AG Grid
- ✏️  Inline editing with validation
- 💾 Writeback to Databricks Lakebase
- 📈 Stock optimization recommendations
- 🎨 Modern UI with Dash Mantine Components

### MCP Server
- 🤖 AI-powered data analysis tools
- 🔍 Unity Catalog metadata exploration
- 📊 SQL query execution
- 🧠 LLM-powered insights

## Deployment

### Deploy to Databricks Apps

```bash
# Deploy both apps
databricks bundle deploy

# Deploy individually
databricks bundle deploy --resource apps.excel_writeback_ui
databricks bundle deploy --resource apps.excel_writeback_mcp
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## Project Structure

```
excel-writeback-apx/
├── src/excel_writeback/
│   └── backend/
│       ├── app.py              # Main Dash application
│       ├── mcp_standalone.py   # Standalone MCP server
│       ├── pages/              # Dash pages
│       ├── callbacks/          # Dash callbacks
│       ├── components/         # Dash components
│       ├── mcp/                # MCP tools
│       ├── database.py         # Lakebase connection
│       └── models.py           # Data models
├── databricks.yml              # DAB configuration
├── ui_app/                     # UI app deployment
│   └── app.yaml               # UI permissions (restricted)
├── mcp_app/                    # MCP app deployment
│   └── app.yaml               # MCP permissions (elevated)
├── run_dev.sh                  # Dev server script
└── run_mcp.sh                  # MCP server script
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
LAKEBASE_DATABASE=your-database
LAKEBASE_SCHEMA=your-schema
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
1. Edit files in `src/excel_writeback/backend/`
2. Uvicorn auto-reloads on save
3. Test in browser

### Add New Dash Pages
1. Create file in `src/excel_writeback/backend/pages/`
2. Use Dash `register_page()` decorator
3. Add callbacks in `src/excel_writeback/backend/callbacks/`

### Add MCP Tools
1. Add tool functions in `src/excel_writeback/backend/mcp/tools.py`
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
2. Test locally with `./run_dev.sh`
3. Validate DAB: `databricks bundle validate`
4. Submit PR

## License

Internal Databricks Solutions Accelerator

## Support

For issues or questions, contact the Databricks Solutions Architecture team.
