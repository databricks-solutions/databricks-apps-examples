# Deployment Guide - Separate UI and MCP Apps

## Architecture Overview

This project now deploys TWO separate Databricks Apps for better security isolation:

### 1. **excel-writeback-ui** (User-Facing Application)
- **Purpose**: Dash-based UI for data editing
- **Endpoints**:
  - `/` - Redirects to Dash app
  - `/dash` - Main Dash interface
  - `/api` - REST API endpoints
- **Permissions**: Restricted (CAN_CONNECT to database, CAN_USE warehouse)
- **Entry Point**: `excel_writeback.backend.app:app`

### 2. **excel-writeback-mcp** (MCP Server - Elevated Privileges)
- **Purpose**: Model Context Protocol server for AI tooling
- **Endpoints**:
  - `/mcp` - MCP protocol endpoint
  - `/health` - Health check
- **Permissions**: Elevated (CAN_CONNECT_AND_CREATE, CAN_QUERY LLM)
- **Entry Point**: `excel_writeback.backend.mcp_standalone:app`

## Security Benefits

### Principle of Least Privilege
- UI users cannot directly access MCP's elevated database permissions
- LLM endpoint access isolated to MCP server only
- Clear security boundary between user-facing and AI tooling layers

### Blast Radius Limitation
- Vulnerabilities in UI don't expose MCP capabilities
- MCP performance issues won't impact UI responsiveness
- Independent scaling and monitoring

### Audit & Compliance
- Separate access logs for UI vs MCP usage
- Clear tracking of who accessed what capabilities
- Different authentication boundaries

## Directory Structure

```
excel-writeback-apx/
├── databricks.yml          # DAB config defining both apps
├── src/                    # Shared source code (symlinked)
│   └── excel_writeback/
│       └── backend/
│           ├── app.py              # Main UI app (no MCP)
│           ├── mcp_standalone.py   # Standalone MCP server
│           └── mcp/                # MCP tools
├── ui_app/                 # UI App deployment
│   ├── app.yaml           # UI-specific config & permissions
│   └── src/               # Symlink to ../src
└── mcp_app/                # MCP App deployment
    ├── app.yaml           # MCP-specific config & permissions
    └── src/               # Symlink to ../src
```

## Deployment Commands

### Deploy Both Apps
```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/excel-writeback-apx
databricks bundle deploy
```

This deploys BOTH apps in one command:
- `excel-writeback-ui-{username}`
- `excel-writeback-mcp-{username}`

### Deploy Individual Apps
```bash
# Deploy only UI app
databricks bundle deploy --resource apps.excel_writeback_ui

# Deploy only MCP server
databricks bundle deploy --resource apps.excel_writeback_mcp
```

### Run Apps
```bash
# After deployment, find the app URLs in Databricks workspace:
# Workspace -> Apps -> excel-writeback-ui-{username}
# Workspace -> Apps -> excel-writeback-mcp-{username}
```

## Configuration Files

### databricks.yml
Main DAB configuration that defines both app resources

### ui_app/app.yaml
- Restricted database permissions (CAN_CONNECT)
- Access to SQL Warehouse
- No LLM endpoint access
- Runs `excel_writeback.backend.app:app`

### mcp_app/app.yaml
- Elevated database permissions (CAN_CONNECT_AND_CREATE)
- Access to SQL Warehouse
- Access to LLM endpoint (CAN_QUERY)
- Runs `excel_writeback.backend.mcp_standalone:app`

## Development Workflow

### Local Development
```bash
# UI + API (no MCP)
uv run uvicorn excel_writeback.backend.app:app --reload

# MCP Server standalone
uv run uvicorn excel_writeback.backend.mcp_standalone:app --reload --port 8001
```

### Making Changes
1. Update code in `src/excel_writeback/`
2. Symlinks automatically reflect changes in both app directories
3. Deploy with `databricks bundle deploy`

## Validation
```bash
databricks bundle validate
```

## Monitoring

Check app status:
```bash
# List all apps
databricks apps list

# Get specific app status
databricks apps get excel-writeback-ui-{username}
databricks apps get excel-writeback-mcp-{username}
```

## Rollback Strategy

If issues arise, redeploy previous version or delete specific app:
```bash
databricks apps delete excel-writeback-mcp-{username}
```

This allows UI to continue running while MCP is fixed.

## Future Enhancements

- Add app-level networking policies
- Implement rate limiting per app
- Configure different auto-scaling profiles
- Set up separate monitoring dashboards
