# Coles Inventory Intelligence MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with access to inventory forecasts and stock optimization data from Databricks Lakebase PostgreSQL.

## Overview

This MCP server enables AI assistants (like Claude) to query and analyze inventory data through natural language. It connects to the same PostgreSQL database as the Coles Inventory Intelligence Dash application, providing tools for:

- **Forecast Discovery**: List available forecast runs
- **Optimization Results**: Query stock optimization recommendations
- **Restocking Recommendations**: Get prioritized restocking suggestions
- **Category Insights**: Analyze performance by product category
- **Forecast Comparison**: Compare results between forecast runs
- **Product Details**: Get historical data for specific products

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Databricks AI Playground                       │
│                   Claude / AI Agents                             │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP Protocol
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              inventory-mcp-server (This App)                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    MCP Tools                             │   │
│  │  • get_forecast_runs()      • recommend_restocking()    │   │
│  │  • get_optimization_results() • get_category_insights() │   │
│  │  • compare_forecasts()      • get_product_details()     │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ SQL Queries
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Databricks Lakebase PostgreSQL                      │
│              excel_app.stock_optimization_results               │
└─────────────────────────────────────────────────────────────────┘
```

## Available Tools

### Data Query Tools

| Tool | Description |
|------|-------------|
| `health` | Check server and database connectivity |
| `get_current_user` | Get authenticated user information |
| `get_forecast_runs` | List all available forecast runs with optimization results |
| `get_optimization_results` | Get detailed optimization results for a specific forecast |
| `recommend_restocking` | Get prioritized restocking recommendations |
| `get_category_insights` | Analyze a product category across all forecasts |
| `compare_forecasts` | Compare optimization results between two forecasts |
| `get_product_details` | Get historical optimization data for a product |

### ML Model Invocation Tools

Following the [Databricks Apps Cookbook pattern](https://apps-cookbook.dev/docs/dash/aiml/ml_serving_invoke):

| Tool | Description |
|------|-------------|
| `invoke_stock_optimizer` | Call ML stock optimization model via Model Serving |
| `generate_inventory_insights` | Generate AI insights using LLM endpoint |
| `run_demand_forecast` | Run demand forecasting for a category |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Databricks CLI configured: `databricks configure --token`
- Access to the Lakebase PostgreSQL database

### Run Locally

```bash
# 1. Navigate to the project
cd mcp-inventory-server

# 2. Install dependencies
uv sync

# 3. Set environment variables
export LAKEBASE_INSTANCE_NAME=daveok
export LAKEBASE_DATABASE=databricks_postgres
export LAKEBASE_SCHEMA=excel_app

# 4. Start the server
uv run inventory-mcp-server

# Server runs at http://localhost:8000
# MCP endpoint: http://localhost:8000/mcp
# API docs: http://localhost:8000/docs
```

### Deploy to Databricks Apps

```bash
# 1. Create the app
databricks apps create inventory-mcp-server

# 2. Deploy
databricks apps deploy inventory-mcp-server --source-code-path /Workspace/Users/your.email@databricks.com/apps/inventory-mcp-server
```

Or use Databricks Asset Bundles (see `databricks.yml`).

## Testing in AI Playground

1. Deploy the MCP server to Databricks Apps
2. Navigate to **AI Playground** in your Databricks workspace
3. Select a model with **Tools enabled**
4. Click **Tools > + Add tool** and select `inventory-mcp-server`
5. Start asking questions about inventory data:

**Example prompts:**
- "What forecast runs are available?"
- "Show me the optimization results for the latest dairy forecast"
- "What products should I prioritize restocking?"
- "Compare the last two forecast runs - what changed?"
- "Give me insights on the Frozen category"

## Project Structure

```
mcp-inventory-server/
├── server/
│   ├── __init__.py           # Package initialization
│   ├── app.py                # FastMCP + FastAPI setup
│   ├── main.py               # Entry point
│   ├── tools.py              # MCP tool definitions (11 tools)
│   └── utils.py              # Database & auth helpers
├── scripts/dev/
│   ├── start_server.sh       # Start server locally
│   └── example_agent.py      # CLI agent demo
├── notebooks/
│   └── mcp_agent_demo.py     # Databricks notebook demo
├── tests/
│   └── test_tools.py         # Integration tests
├── app.yaml                  # Databricks Apps configuration
├── databricks.yml            # DAB deployment configuration
├── pyproject.toml            # Python project configuration
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

## Agent Notebook

The `notebooks/mcp_agent_demo.py` notebook demonstrates:

1. **MCP Server Connection** - Connect to the deployed MCP server
2. **Tool Discovery** - List all 11 available tools
3. **Direct Tool Calls** - Call individual MCP tools
4. **OpenAI Agent** - Create an AI agent with tool calling
5. **Interactive Queries** - Natural language inventory analysis

Import the notebook into Databricks and run it to see the agent in action.

Based on [OpenAI MCP Tool Calling Agent](https://docs.databricks.com/aws/en/notebooks/source/generative-ai/openai-mcp-tool-calling-agent.html).

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LAKEBASE_INSTANCE_NAME` | Lakebase PostgreSQL instance name | `daveok` |
| `LAKEBASE_DATABASE` | Database name | `databricks_postgres` |
| `LAKEBASE_SCHEMA` | Schema name | `excel_app` |
| `PGHOST` | PostgreSQL host (auto-detected if not set) | - |
| `PGUSER` | PostgreSQL user (auto-detected if not set) | - |

### Database Resources

The server requires access to:
- **PostgreSQL Database**: Lakebase instance for data storage
- **SQL Warehouse**: For workspace authentication (optional)

## Development

### Code Formatting

```bash
# Format code
uv run ruff format .

# Check for lint errors
uv run ruff check .
```

### Running Tests

```bash
uv run pytest tests/
```

### Adding New Tools

1. Open `server/tools.py`
2. Add a new function with the `@mcp_server.tool` decorator:

```python
@mcp_server.tool
def my_new_tool(param: str) -> dict:
    """
    Description of what the tool does.
    
    Args:
        param: Description of the parameter
        
    Returns:
        dict: Description of the return value
    """
    # Implementation
    return {"result": "value"}
```

3. Restart the server - the tool is automatically available

## Related Projects

- **excel-the-dash-way**: Dash web application for inventory management
- [Databricks MCP Documentation](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://modelcontextprotocol.io)

## License

© 2026 Databricks, Inc. All rights reserved.

