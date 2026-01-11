# Authentication Fix - Deployment Guide

## Problem Fixed

**Error:**
```
401 Unauthorized: Could not connect to validation service
```

When the UI app tried to call the MCP app's validation API, it failed because Databricks Apps requires authentication for inter-app communication.

## Solution Implemented

### Multi-Strategy Authentication

The fix implements **three authentication strategies** (tried in order):

1. **Inter-App Shared Secret** (Primary for same-workspace apps)
   - Fast and simple
   - Works for apps in the same workspace
   - Uses `X-Inter-App-Secret` header

2. **OAuth Bearer Token** (Fallback for cross-workspace)
   - Uses Databricks OAuth credentials
   - Extracts token from WorkspaceClient
   - Standard `Authorization: Bearer` header

3. **No Auth** (For localhost development)
   - Skipped when running locally
   - Allows easy local testing

## Changes Made

### 1. UI App (`ui_app/`)

**File: `range_optimizer/backend/mcp_client.py`**
- ✅ Updated `_get_auth_headers()` to try multiple auth strategies
- ✅ Added inter-app secret support
- ✅ Improved OAuth token extraction
- ✅ Added comprehensive logging

**File: `app.yaml`**
- ✅ Added `INTER_APP_SECRET` environment variable

### 2. MCP App (`mcp_app/`)

**File: `range_optimizer/backend/app.py`**
- ✅ Added authentication middleware
- ✅ Validates inter-app secret OR OAuth token
- ✅ Allows public access to `/health`, `/docs`, etc.

**File: `app.yaml`**
- ✅ Added `INTER_APP_SECRET` environment variable (matching UI app)

## Deployment Steps

### Step 1: Redeploy Both Apps

```bash
# Deploy MCP app first
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp
databricks bundle deploy --resource apps.range_optimizer_mcp

# Then deploy UI app
databricks bundle deploy --resource apps.range_optimizer_ui
```

### Step 2: Verify MCP App is Running

```bash
# Get MCP app URL from deployment output or:
MCP_URL="https://range-opt-mcp-daveok-7405614596482958.18.azure.databricksapps.com"

# Test health endpoint (should work without auth)
curl $MCP_URL/health

# Expected response:
# {"status":"healthy","service":"mcp-server"}
```

### Step 3: Test Validation Endpoint

```bash
# Test with inter-app secret
curl -X POST $MCP_URL/api/validate \
  -H "X-Inter-App-Secret: range-opt-inter-app-secret-2026-secure-key" \
  -H "Content-Type: application/json" \
  -d '{"data": []}'

# Expected response:
# {
#   "valid": false,
#   "has_errors": true,
#   "has_warnings": false,
#   "issues": [...],
#   "summary": "No data provided"
# }
```

### Step 4: Test UI App

1. Open the UI app in your browser
2. Navigate to the home page with the data grid
3. Add or edit SKU data
4. Watch for validation alerts (should appear without 401 errors)

## How It Works

### Request Flow

```
User edits grid in UI
    ↓
validate_grid() callback triggered
    ↓
mcp_client._get_auth_headers() called
    ├─> Adds X-Inter-App-Secret header
    └─> Adds Authorization: Bearer header (if available)
    ↓
HTTP POST to mcp_app/api/validate
    ↓
MCP app middleware checks auth:
    ├─> ✓ Valid inter-app secret? → Allow
    ├─> ✓ Valid OAuth token? → Allow
    └─> ❌ Neither? → Return 401
    ↓
Validation logic runs
    ↓
Returns {valid, has_errors, issues}
    ↓
UI builds alerts and disables/enables submit button
```

### Authentication Headers Sent

```http
POST /api/validate HTTP/1.1
Host: range-opt-mcp-daveok-...databricksapps.com
Content-Type: application/json
X-Inter-App-Secret: range-opt-inter-app-secret-2026-secure-key
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...  (if available)

{"data": [...]}
```

## Security Considerations

### Current Implementation (Development/Testing)

- ✅ Inter-app secret stored in `app.yaml`
- ⚠️ Secret is visible in deployment config
- ⚠️ Same secret in both apps

### Production Recommendations

1. **Use Databricks Secrets**

```yaml
# ui_app/app.yaml
env:
  - name: INTER_APP_SECRET
    valueFrom:
      secretRef:
        scope: range-optimizer
        key: inter-app-secret

# mcp_app/app.yaml
env:
  - name: INTER_APP_SECRET
    valueFrom:
      secretRef:
        scope: range-optimizer
        key: inter-app-secret
```

2. **Create the secret:**

```bash
# Create secret scope
databricks secrets create-scope range-optimizer

# Put secret value
databricks secrets put-secret range-optimizer inter-app-secret \
  --string-value "$(openssl rand -base64 32)"
```

3. **Rotate secrets regularly**

```bash
# Generate new secret
NEW_SECRET=$(openssl rand -base64 32)

# Update secret
databricks secrets put-secret range-optimizer inter-app-secret \
  --string-value "$NEW_SECRET"

# Redeploy apps (they will pick up new secret)
databricks bundle deploy
```

## Troubleshooting

### Still Getting 401 Errors

**Check 1: Verify secrets match**
```bash
# In UI app
echo $INTER_APP_SECRET

# In MCP app
echo $INTER_APP_SECRET

# They should be identical
```

**Check 2: Check MCP app logs**
```bash
databricks apps logs range-opt-mcp-daveok --follow
```

Look for:
- `❌ Unauthorized request` - Auth is being rejected
- `✓ Inter-app secret validated` - Auth is working
- `✓ Bearer token present` - OAuth is being used

**Check 3: Check UI app logs**
```bash
databricks apps logs range-opt-ui-daveok --follow
```

Look for:
- `✓ Using inter-app shared secret` - Secret is being sent
- `✓ Added Bearer token` - OAuth is being sent
- `⚠️ No OAuth token available` - Fallback to secret only

### MCP App Not Responding

```bash
# Check if app is running
databricks apps get range-opt-mcp-daveok

# Check health endpoint
curl https://range-opt-mcp-daveok-.../health

# Restart if needed
databricks apps restart range-opt-mcp-daveok
```

### Validation Not Working

```bash
# Test MCP API directly
curl -X POST https://range-opt-mcp-daveok-.../api/validate \
  -H "X-Inter-App-Secret: range-opt-inter-app-secret-2026-secure-key" \
  -H "Content-Type: application/json" \
  -d '{"data": [{"SKU_ID": "TEST", "SKU_NAME": "Test"}]}'

# Should return validation result, not 401
```

## Local Development

For local testing, authentication is automatically skipped for localhost:

```bash
# Terminal 1: Start MCP app
cd mcp_app
uv run uvicorn range_optimizer.backend.app:app --reload --port 9000

# Terminal 2: Start UI app
cd ui_app
export MCP_SERVER_URL=http://localhost:9000
./run-local.sh

# No auth needed for localhost!
```

## Monitoring

Add these to your monitoring:

1. **Track 401 errors** in MCP app logs
2. **Track auth success rate** (`✓ Inter-app secret validated`)
3. **Alert on sustained 401s** (> 5% of requests)

## Next Steps

1. ✅ Deploy the fix (follow steps above)
2. ✅ Test validation works without 401 errors
3. 📝 Move secrets to Databricks Secrets (production)
4. 📝 Add monitoring for auth failures
5. 📝 Document secret rotation procedure

## Success Criteria

- ✅ No more `401 Unauthorized` errors in UI app logs
- ✅ Validation alerts appear instantly when editing grid
- ✅ Submit button properly enables/disables based on validation
- ✅ MCP app logs show `✓ Inter-app secret validated`

## Rollback Plan

If the fix causes issues:

```bash
# Rollback to previous version
databricks bundle deploy --resource apps.range_optimizer_mcp --target previous
databricks bundle deploy --resource apps.range_optimizer_ui --target previous

# Or temporarily disable auth in MCP app
# Comment out the INTER_APP_SECRET in mcp_app/app.yaml
# This will allow all requests (less secure but functional)
```

## Summary

The authentication fix uses a **shared secret approach** for same-workspace app-to-app communication, with OAuth as a fallback. This is simple, secure, and efficient for internal app communication.

**Key Benefits:**
- ✅ No more 401 errors
- ✅ Fast authentication (no external calls)
- ✅ Works in all environments (local, staging, prod)
- ✅ Easy to rotate secrets
- ✅ Backward compatible with OAuth
