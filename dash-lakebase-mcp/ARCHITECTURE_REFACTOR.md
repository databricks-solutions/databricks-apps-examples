# Architecture Refactor: MCP Backend API

## Overview

Refactored the `dash-lakebase-mcp` project to eliminate code duplication and establish a clean API-based architecture.

## Previous Architecture (Problematic)

```
ui_app/                    mcp_app/
├── Dash UI               ├── Dash UI (duplicate!)
├── Callbacks             ├── Callbacks (duplicate!)
├── Components            ├── Components (duplicate!)
├── Pages                 ├── Pages (duplicate!)
└── Database (restricted) ├── Database (elevated)
                          └── MCP Server
```

**Problems:**
- ❌ Duplicate Dash UI code in both apps
- ❌ Duplicate callbacks and components
- ❌ Validation logic duplicated
- ❌ Maintenance nightmare (fix bugs twice)
- ❌ Unclear separation of concerns

## New Architecture (Clean)

```
ui_app/                    mcp_app/
├── Dash UI               ├── FastAPI Backend API
├── Callbacks             ├── REST Endpoints:
├── Components            │   ├── POST /api/validate
├── Pages                 │   ├── POST /api/run_optimization
└── MCP Client ──────────>│   ├── GET  /api/layout-data
    (API calls)           │   ├── POST /api/forecasts
                          │   └── GET  /api/forecasts/{id}/optimization
                          ├── Database (elevated permissions)
                          └── MCP Server (AI tools)
```

**Benefits:**
- ✅ Single source of truth for business logic
- ✅ Clean API-based communication
- ✅ No code duplication
- ✅ Easy to test (mock API responses)
- ✅ Clear separation of concerns
- ✅ Scalable architecture

## Key Changes

### 1. MCP App - Pure Backend API

**Removed:**
- ❌ All Dash UI code (`callbacks/`, `pages/`, `components/`)
- ❌ Dash app initialization in `app.py`
- ❌ WSGI middleware mounting

**Added:**
- ✅ Validation API endpoint (`POST /api/validate`)
- ✅ Optimization API endpoint (`POST /api/run_optimization`)
- ✅ CORS middleware for cross-origin requests
- ✅ Health check endpoint (`/health`)
- ✅ Root endpoint with API documentation (`/`)

**File: `mcp_app/range_optimizer/backend/app.py`**
```python
# Now a pure FastAPI backend
app = FastAPI(
    title=f"{conf.app_name} MCP Server",
    description="Backend API with elevated permissions",
    lifespan=lifespan,
)

# CORS for UI app to call this API
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Just API routes, no Dash UI
app.include_router(api)
```

**File: `mcp_app/range_optimizer/backend/router.py`**
```python
@api.post("/validate", response_model=ValidationResult)
async def validate_data(request: ValidationRequest):
    """Validate grid data for errors and warnings"""
    # Centralized validation logic
    # Returns: {valid: bool, has_errors: bool, issues: [...]}
    
@api.post("/run_optimization")
async def run_optimization(payload: dict):
    """Run EOQ-based optimization model"""
    # 1. Read forecast data
    # 2. Run optimization
    # 3. Write results
    # Returns: {status, forecast_id, product_count}
```

### 2. UI App - Calls MCP API

**Updated:**
- ✅ `mcp_client.py` - Added `validate_data()` function
- ✅ `input_callbacks.py` - Calls MCP API for validation
- ✅ `build_validation_summary()` - Uses API response to build alerts

**File: `ui_app/range_optimizer/backend/mcp_client.py`**
```python
def validate_data(data: List[Dict[str, Any]]) -> APIResponse:
    """Validate grid data via MCP server"""
    response = requests.post(
        f"{mcp_url}/api/validate",
        json={"data": data},
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    return APIResponse(success=True, data=response.json())
```

**File: `ui_app/range_optimizer/backend/callbacks/input_callbacks.py`**
```python
def build_validation_summary(data):
    """Run validation via MCP API"""
    response = validate_data(data)  # Call MCP API
    
    if not response.success:
        # Show error but don't block submission
        return error_alert, False
    
    # Parse validation results
    validation_result = response.data
    issues = validation_result.get("issues", [])
    
    # Build alerts from issues
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    
    # Create Dash alerts
    alerts = create_alerts(errors, warnings)
    disable_submit = validation_result.get("has_errors", False)
    
    return alert_stack, disable_submit
```

### 3. Validation Logic - Centralized

**Before:** Duplicated in both apps' `components/input.py`

**After:** Single implementation in MCP API

**File: `mcp_app/range_optimizer/backend/router.py`**
```python
@api.post("/validate")
async def validate_data(request: ValidationRequest):
    issues = []
    
    # Check required fields
    for i, row in enumerate(request.data):
        missing = [f for f in REQUIRED_FIELDS if not row.get(f)]
        if missing:
            issues.append(ValidationIssue(
                row_index=i,
                sell_id=row.get("SKU_ID"),
                severity="error",
                message=f"Missing: {', '.join(missing)}"
            ))
    
    # Check integer fields
    for field in INTEGER_FIELDS:
        if not is_valid_integer(row.get(field)):
            issues.append(ValidationIssue(...))
    
    # Check duplicates
    if has_duplicate_sku_ids(request.data):
        issues.append(ValidationIssue(...))
    
    return ValidationResult(
        valid=not has_errors,
        has_errors=len(errors) > 0,
        has_warnings=len(warnings) > 0,
        issues=issues,
        summary=build_summary(errors, warnings)
    )
```

## API Endpoints

### MCP Server (Port 9000/9001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information and documentation |
| GET | `/health` | Health check |
| GET | `/docs` | OpenAPI/Swagger docs |
| POST | `/api/validate` | Validate grid data |
| POST | `/api/run_optimization` | Run optimization model |
| GET | `/api/categories` | List categories |
| GET | `/api/layout-data` | Get SKU data |
| POST | `/api/layout-data` | Save SKU data |
| POST | `/api/forecasts` | Submit forecast |
| GET | `/api/forecasts` | List forecasts |
| GET | `/api/forecasts/{id}/optimization` | Get optimization results |

### UI App (Port 8002/8003)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dash UI home page |
| GET | `/stock-optimization` | Optimization results page |
| GET | `/about` | About page |

## Data Flow

### Validation Flow

```
User edits grid
    ↓
ui_app callback triggered
    ↓
validate_grid() called
    ↓
mcp_client.validate_data(data)
    ↓
HTTP POST to mcp_app/api/validate
    ↓
Validation logic runs in MCP
    ↓
Returns {valid, has_errors, issues}
    ↓
ui_app builds Dash alerts
    ↓
Submit button disabled if errors
```

### Optimization Flow

```
User clicks Submit
    ↓
ui_app callback triggered
    ↓
mcp_client.submit_optimization_run(data)
    ↓
HTTP POST to mcp_app/api/forecasts
    ↓
MCP writes to optimization_runs table
    ↓
MCP triggers optimization
    ↓
HTTP POST to mcp_app/api/run_optimization
    ↓
EOQ model runs
    ↓
Results written to opt_planogram table
    ↓
Returns {status, forecast_id, product_count}
    ↓
ui_app shows success message
```

## Environment Variables

### UI App
```bash
MCP_SERVER_URL=http://localhost:9000  # Points to MCP backend
```

### MCP App
```bash
# Database credentials (elevated permissions)
PGHOST=...
PGDATABASE=...
PGUSER=...
```

## Testing

### Test MCP API Directly

```bash
# Start MCP server
cd mcp_app
uv run uvicorn range_optimizer.backend.app:app --reload --port 9000

# Test validation endpoint
curl -X POST http://localhost:9000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"data": [{"SKU_ID": "SKU001", "SKU_NAME": "Test"}]}'

# Test optimization endpoint
curl -X POST http://localhost:9000/api/run_optimization \
  -H "Content-Type: application/json" \
  -d '{"forecast_id": "RUN-20260112-abc123"}'

# View API docs
open http://localhost:9000/docs
```

### Test Full Stack

```bash
# Terminal 1: Start MCP server
cd mcp_app
./run-local.sh

# Terminal 2: Start UI app
cd ui_app
MCP_SERVER_URL=http://localhost:9001 ./run-local.sh

# Access UI
open http://localhost:8003
```

## Migration Guide

### For Developers

1. **No more duplicate code** - All validation logic is in MCP API
2. **Use mcp_client** - Never access database directly from ui_app
3. **Add new validations** - Update `mcp_app/router.py` only
4. **Test APIs** - Use `/docs` endpoint for interactive testing

### For Deployment

1. **Deploy MCP app first** - Ensure API is available
2. **Deploy UI app** - Set `MCP_SERVER_URL` environment variable
3. **Check connectivity** - UI app must be able to reach MCP API

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| Code duplication | ❌ High | ✅ None |
| Validation logic | ❌ 2 copies | ✅ 1 copy (API) |
| Testing | ❌ Hard | ✅ Easy (mock API) |
| Maintenance | ❌ Fix twice | ✅ Fix once |
| Scalability | ❌ Limited | ✅ High |
| Separation of concerns | ❌ Unclear | ✅ Clear |
| API documentation | ❌ None | ✅ OpenAPI/Swagger |

## Next Steps

1. ✅ Remove Dash UI from mcp_app
2. ✅ Create validation API endpoint
3. ✅ Create optimization API endpoint
4. ✅ Update ui_app to call MCP API
5. ⏳ Test the refactored architecture
6. 📝 Update deployment scripts
7. 📝 Add API integration tests
8. 📝 Update documentation

## Files Changed

### MCP App
- ✅ `mcp_app/range_optimizer/backend/app.py` - Removed Dash, pure FastAPI
- ✅ `mcp_app/range_optimizer/backend/router.py` - Added validation & optimization endpoints
- ✅ `mcp_app/range_optimizer/backend/models.py` - Added ValidationRequest/Result models
- ❌ `mcp_app/range_optimizer/backend/callbacks/` - Deleted (no longer needed)
- ❌ `mcp_app/range_optimizer/backend/pages/` - Deleted (no longer needed)
- ❌ `mcp_app/range_optimizer/backend/components/` - Deleted (no longer needed)

### UI App
- ✅ `ui_app/range_optimizer/backend/mcp_client.py` - Added validate_data() function
- ✅ `ui_app/range_optimizer/backend/callbacks/input_callbacks.py` - Uses MCP API for validation

## Conclusion

This refactor eliminates code duplication, establishes a clean API-based architecture, and makes the system more maintainable and scalable. The MCP app is now a pure backend API server with elevated permissions, while the UI app focuses solely on the user interface and delegates all business logic to the MCP API.
