# AGENTS.md - Range Optimizer Development Guide

This repository contains a Python-based range optimization system with two main components: a Dash UI application and an MCP (Model Context Protocol) server. Both applications use FastAPI backends with PostgreSQL connectivity.

## 🏗️ Architecture

### Dual-Application Structure
- **UI App** (`ui_app/`): Dash-based web interface with data grid components
  - Serves at `http://localhost:8003` (default)
  - FastAPI backend with Dash UI at `/` and REST API at `/api`
  - Restricted database permissions
- **MCP App** (`mcp_app/`): Standalone MCP server for AI tooling
  - Serves at `http://localhost:9001` (default) 
  - Elevated permissions for optimization and AI operations
  - Used by Claude Desktop and other MCP clients

## 🚀 Build/Test Commands

### Development Environment
- **Python version**: 3.11+
- **Package manager**: `uv` (always use `uv`, never `pip`)
- **Environment variables**: Load from `.env` in project root

### Running Applications
```bash
# Start both apps simultaneously (recommended)
./start-all-apps.sh

# Start individual apps with custom ports
./run-databricks-app-local.sh mcp_app 9000 9001 username
./run-databricks-app-local.sh ui_app 9002 9003 username

# Stop all apps
./stop-all-apps.sh
```

### Testing Commands
```bash
# Run all validation tests
uv run python test_validation.py

# Run MCP API tests (requires server running at localhost:9001)
uv run python test_mcp_api.py

# Run a single test file with pytest
uv run pytest mcp_app/scripts/test_model.py

# Run a specific test function
uv run pytest mcp_app/scripts/test_model.py::test_model -v

# Run tests with output
uv run pytest -v -s mcp_app/scripts/test_model.py
```

### Development Workflow
```bash
# Install dependencies for specific app
cd ui_app && uv sync
cd mcp_app && uv sync

# Monitor logs during development
tail -f mcp-app.log ui-app.log

# Filter for errors/warnings
tail -f mcp-app.log | grep -E "ERROR|WARNING"
```

## 📋 Code Style Guidelines

### Import Organization
```python
# Standard library imports first
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Third-party imports next
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
import pandas as pd

# Local imports last
from .config import conf
from .logger import logger
from .models import BaseModel
```

### Type Annotations
- **Always use type hints** for function parameters and return values
- Import types from `typing` module when needed
- Use Pydantic models for API input/output
- Prefer `Optional[T]` over `Union[T, None]`

### Naming Conventions
- **Files**: `snake_case.py` (e.g., `stock_optimization.py`)
- **Classes**: `PascalCase` (e.g., `StockOptimizer`, `LayoutDataIn`)
- **Functions/Variables**: `snake_case` (e.g., `get_optimization_results`, `api_url`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `API_PREFIX`, `DEFAULT_TIMEOUT`)
- **Endpoints**: `kebab-case` (e.g., `/optimization-results`)

### Error Handling
```python
# Use structured error responses
raise HTTPException(status_code=400, detail="Invalid input format")

# Database operations should handle connection errors
try:
    result = query_df(sql_query, params)
except DatabaseError as e:
    logger.error(f"Database query failed: {e}")
    raise HTTPException(status_code=500, detail="Database operation failed")
```

### Configuration Management
- Use Pydantic Settings for configuration
- Support both environment variables and `.env` files
- Centralize configuration in `config.py` modules
- Use computed fields for derived settings

## 🏛️ API Design Patterns

### 3-Model Pattern
Follow the established pattern for data models:
- **Entity**: Database model (e.g., `LayoutData`)
- **EntityIn**: Input model for creation/updates (e.g., `LayoutDataIn`)
- **EntityOut**: Output model for API responses (e.g., `LayoutDataOut`)

### API Endpoints
```python
# Always include response_model and operation_id
@router.post("/forecasts/", response_model=ForecastSubmissionOut, operation_id="submit_forecast")
async def submit_forecast(forecast: ForecastSubmissionIn):
    # Implementation
    pass

# Use proper HTTP status codes and error handling
@router.get("/optimization-results/{result_id}", response_model=OptimizationResultsOut)
async def get_optimization_result(result_id: str):
    result = get_result_by_id(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
```

### Database Operations
- Use connection pooling with `psycopg`
- Prefer `query_df()` for data retrieval (returns pandas DataFrame)
- Use parameterized queries to prevent SQL injection
- Implement proper transaction handling for writes

```python
from .database import query_df, query_dict_list, bulk_insert

# Read operations
df = query_df("SELECT * FROM optimization_results WHERE date >= %s", [start_date])

# Write operations  
bulk_insert("forecast_submissions", data_dict_list)
```

## 🎨 UI Development (Dash)

### Component Structure
- Group components by functionality in `/components/` directory
- Use dash-mantine-components for UI elements
- Implement callbacks in separate `/callbacks/` modules
- Use dash-ag-grid for data tables with advanced features

### Page Organization
- Pages in `/pages/` directory become automatic Dash routes
- Use `page_container` for page layout
- Implement loading states and error boundaries
- Separate layout from callback logic

```python
# pages/stock_optimization.py
from dash import html, dcc, register_page
from dash_mantine_components import dmc

register_page(__name__, path="/stock-optimization")

def layout():
    return dmc.Container([
        dmc.Title("Stock Optimization", order=2),
        # Component layout
    ])
```

## 🔧 MCP Server Development

### Tool Implementation
- Implement tools in `/mcp/tools.py` following MCP protocol
- Use FastAPI for HTTP endpoints alongside MCP transport
- Maintain security isolation - MCP server has elevated permissions
- Include proper error responses and logging

### AI Integration
- Use MLflow for model tracking and versioning
- Implement OpenAI integration for AI-powered features
- Cache model results to improve performance
- Include audit logging for all AI operations

## 📊 Logging & Monitoring

### Logging Standards
```python
# Use structured logging with context
logger.info("Processing optimization request", extra={
    "request_id": request_id,
    "user_id": user_id,
    "parameters": params
})

# Include error details
logger.error("Optimization failed", exc_info=True, extra={
    "error_type": type(e).__name__,
    "request_id": request_id
})
```

### Log Monitoring
- Local logs: `mcp-app.log`, `ui-app.log`
- Databricks logs: `databricks apps logs <app-name> --follow`
- Use grep for filtering: `tail -f app.log | grep -E "ERROR|WARNING"`

## 🧪 Testing Guidelines

### Test Organization
- Unit tests in same directory as module (e.g., `test_model.py`)
- Integration tests for API endpoints
- Use `pytest` framework with fixtures for database connections
- Mock external dependencies (Databricks SDK, MLflow)

### Test Data
- Use sample data generation utilities in `sample_data.py`
- Test with edge cases and error conditions
- Include performance tests for optimization algorithms

## 🔄 Development Workflow

### Before Making Changes
1. Run the development servers: `./start-all-apps.sh`
2. Check existing tests pass: `python test_validation.py`
3. Review similar code patterns in the codebase

### After Making Changes
1. Run tests to verify functionality
2. Test both apps in browser
3. Check logs for any errors or warnings
4. Update documentation if needed

### Code Review Checklist
- [ ] Type annotations complete
- [ ] Error handling implemented  
- [ ] Logging statements included
- [ ] Tests added for new functionality
- [ ] Documentation updated
- [ ] No hardcoded configuration values