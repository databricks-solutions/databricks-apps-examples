# Fixing Authentication Between Databricks Apps

## Problem

Getting `401 Unauthorized` when UI app calls MCP app validation endpoint:
```
Could not connect to validation service: 401 Client Error: Unauthorized for url: 
https://range-opt-mcp-daveok-7405614596482958.18.azure.databricksapps.com/api/validate
```

## Root Cause

When Databricks App A calls Databricks App B, the request must include valid OAuth credentials. The current implementation tries to use `w.config.authenticate()` which doesn't return the correct format.

## Solution Options

### Option 1: Use App Service Principal Token (Recommended)

Each Databricks App runs with its own service principal. Use that SP's credentials:

```python
def _get_auth_headers() -> Optional[Dict[str, str]]:
    """Get auth headers using app's service principal"""
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        
        # The SDK will automatically use the app's OAuth credentials
        # when making API calls. We need to extract that token.
        
        # Method 1: From environment (if Databricks sets it)
        token = os.environ.get("DATABRICKS_TOKEN")
        
        # Method 2: From WorkspaceClient config
        if not token and hasattr(w.config, 'token'):
            token = w.config.token
        
        # Method 3: Use the API client's auth
        if not token:
            # Make a test call to extract auth
            try:
                w.current_user.me()  # This will authenticate
                # Extract from internal state
                if hasattr(w.api_client, '_token'):
                    token = w.api_client._token
            except:
                pass
        
        if token:
            return {"Authorization": f"Bearer {token}"}
        
        return {}
    except Exception as e:
        print(f"Auth error: {e}")
        return {}
```

### Option 2: Make MCP Endpoints Public

If the MCP app is only accessible within your workspace, you can make specific endpoints public.

**Update `mcp_app/app.yaml`:**
```yaml
# Add to app.yaml
command: ["bash", "entrypoint.sh"]

# Make app accessible without auth (workspace-only)
# NOTE: This exposes the API to anyone in the workspace!
# Only do this if MCP app enforces its own auth or is workspace-internal

# In entrypoint.sh or app config:
env:
  - name: DATABRICKS_SKIP_AUTH
    value: "true"  # If supported by Databricks Apps
```

**WARNING:** This approach removes authentication, making the API accessible to anyone in the workspace.

### Option 3: Use Shared Secret (For Internal Apps)

For apps that only communicate within the same workspace:

**`ui_app/app.yaml`:**
```yaml
env:
  - name: INTER_APP_SECRET
    value: "your-secret-key-here"  # Use Databricks Secrets in production
```

**`mcp_app/app.yaml`:**
```yaml
env:
  - name: INTER_APP_SECRET
    value: "your-secret-key-here"  # Same secret
```

**MCP App - Add middleware:**
```python
from fastapi import Header, HTTPException

@app.middleware("http")
async def verify_inter_app_secret(request, call_next):
    if request.url.path.startswith("/api/"):
        secret = request.headers.get("X-Inter-App-Secret")
        expected = os.environ.get("INTER_APP_SECRET")
        if expected and secret != expected:
            # Allow if has valid OAuth, otherwise reject
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"}
                )
    return await call_next(request)
```

**UI App - Add secret header:**
```python
def _get_auth_headers():
    headers = {}
    secret = os.environ.get("INTER_APP_SECRET")
    if secret:
        headers["X-Inter-App-Secret"] = secret
    return headers
```

### Option 4: Use Databricks SDK's Built-in OAuth (Best Practice)

Use the SDK's `api_client.do()` method which handles auth automatically:

**`ui_app/mcp_client.py`:**
```python
def validate_data(data: List[Dict[str, Any]]) -> APIResponse:
    """Validate via MCP using Databricks SDK"""
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import ApiClient
        
        w = WorkspaceClient()
        mcp_url = _get_mcp_url()
        
        # Remove the protocol and host to get relative path
        # Then use w.api_client.do() which handles auth
        
        # For external URLs, use requests with proper auth
        response = w.api_client.do(
            method="POST",
            path=f"{mcp_url}/api/validate",
            json={"data": data}
        )
        
        return APIResponse(success=True, data=response)
    except Exception as e:
        return APIResponse(success=False, data=None, error=str(e))
```

## Recommended Approach

**For development/testing:** Option 1 (Service Principal Token)

**For production:** Option 4 (SDK's built-in OAuth) or Option 3 (Shared Secret for inter-app calls)

## Implementation Steps

1. **Update `ui_app/mcp_client.py`** with proper auth method
2. **Test locally** with `databricks apps run-local`  
3. **Deploy and test** on Databricks Apps
4. **Monitor logs** to verify authentication works

## Testing

```bash
# Test MCP app directly (should work without auth locally)
curl http://localhost:9000/api/validate \
  -H "Content-Type: application/json" \
  -d '{"data": []}'

# Test with Bearer token
TOKEN=$(databricks auth token)
curl https://range-opt-mcp-daveok.../api/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data": []}'
```

## Debug Steps

1. **Check MCP app logs** - See what authentication error is logged
2. **Check UI app logs** - See what auth headers are being sent
3. **Test MCP endpoint directly** - Verify it works with correct auth
4. **Use Databricks Apps debugging** - Enable verbose logging

```python
# Add to mcp_client.py for debugging
def _get_auth_headers():
    headers = # ... your auth logic
    _log(f"🔐 Auth headers being sent: {list(headers.keys())}")
    if "Authorization" in headers:
        _log(f"🔐 Token length: {len(headers['Authorization'])}")
    return headers
```

## Next Steps

Choose and implement one of the options above, then test the authentication flow.
