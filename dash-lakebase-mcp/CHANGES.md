# Changes Summary - Dual App Architecture

## What Changed

### Before
- **Single Databricks App** with embedded MCP server
- All components (UI, API, MCP) running in one process
- Shared permissions across all functionality
- Security boundary concerns

### After
- **Two Separate Databricks Apps**:
  1. `excel-writeback-ui` - User-facing Dash application
  2. `excel-writeback-mcp` - Standalone MCP server with elevated privileges
- Independent security boundaries
- Principle of least privilege enforced

## Files Created/Modified

### New Files
1. `src/excel_writeback/backend/mcp_standalone.py` - Standalone MCP server entry point
2. `ui_app/` - UI app deployment directory
   - `app.yaml` - UI configuration (restricted permissions)
   - `src/` - Symlink to shared source
3. `mcp_app/` - MCP app deployment directory  
   - `app.yaml` - MCP configuration (elevated permissions)
   - `src/` - Symlink to shared source
4. `DEPLOYMENT.md` - Comprehensive deployment guide
5. `CHANGES.md` - This file

### Modified Files
1. `databricks.yml` - Now defines two app resources instead of one
2. `src/excel_writeback/backend/app.py` - Removed embedded MCP server
   - Removed MCP route mounting
   - Removed MCP lifespan management
   - Removed header capture middleware (was for MCP auth)

### Preserved Files
3. `app.yaml` - Original UI configuration (copied to ui_app/)
4. `app-mcp.yaml` - MCP configuration (copied to mcp_app/)

## Key Architecture Decisions

### 1. Symlinked Source Code
- Both apps use symlinks to `../src` to avoid code duplication
- Single source of truth for business logic
- Easy to maintain and update

### 2. Separate Permissions
**UI App**:
- `CAN_CONNECT` - Database access (read/write via API)
- `CAN_USE` - SQL Warehouse access
- NO access to LLM endpoint

**MCP App**:
- `CAN_CONNECT_AND_CREATE` - Full database access
- `CAN_USE` - SQL Warehouse access
- `CAN_QUERY` - LLM endpoint access

### 3. Independent Deployment
- Deploy both: `databricks bundle deploy`
- Deploy UI only: `databricks bundle deploy --resource apps.excel_writeback_ui`
- Deploy MCP only: `databricks bundle deploy --resource apps.excel_writeback_mcp`

## Security Benefits

1. **Isolation**: UI vulnerabilities can't access MCP's elevated permissions
2. **Least Privilege**: Each app has only permissions it needs
3. **Audit Trail**: Separate logs for UI vs MCP access
4. **Blast Radius**: Issues in one app don't affect the other
5. **Independent Scaling**: Scale each based on its workload

## Next Steps

1. Test deployment:
   ```bash
   databricks bundle validate
   databricks bundle deploy
   ```

2. Verify both apps are running:
   ```bash
   databricks apps list
   ```

3. Access the apps:
   - UI: `https://<workspace>/apps/excel-writeback-ui-<username>`
   - MCP: `https://<workspace>/apps/excel-writeback-mcp-<username>`

4. Configure Claude Desktop to use MCP endpoint

## Rollback

To revert to single-app architecture:
1. Restore original `databricks.yml` and `app.py` from git history
2. Remove `ui_app/` and `mcp_app/` directories
3. Delete `mcp_standalone.py`
4. Deploy with original configuration
