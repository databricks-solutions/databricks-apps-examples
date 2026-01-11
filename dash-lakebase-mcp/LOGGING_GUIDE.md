# Logging Guide - Range Optimizer Apps

This guide explains how to monitor logs for the Range Optimizer applications in both local development and Databricks deployment environments.

## Overview

The Range Optimizer consists of two applications:
- **MCP App** (`range-opt-mcp-daveok`): Backend API with elevated database privileges
- **UI App** (`range-opt-ui-daveok`): Frontend Dash application

Each app has separate logging in both local and Databricks environments.

## Architecture

### Local Development
- Logs are written to **local files** in the project directory
- Files: `mcp-app.log` and `ui-app.log`
- Storage: `/Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp/`

### Databricks Deployment
- Logs are stored in **Databricks Apps platform**
- Accessed via Databricks CLI
- Storage: Cloud-based, managed by Databricks
- **No conflict with local logs** (different storage locations)

---

## Local Development Logging

### Starting Apps with Logging

```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp

# Start both apps (logs written to mcp-app.log and ui-app.log)
./start-all-apps.sh

# Start with hot reload enabled
./start-all-apps.sh --dev
```

### Viewing Local Logs

#### Stream MCP App Logs
```bash
tail -f mcp-app.log
```

#### Stream UI App Logs
```bash
tail -f ui-app.log
```

#### View Last 100 Lines and Follow
```bash
tail -n 100 -f mcp-app.log
```

#### Monitor Both Apps Simultaneously
```bash
# Option 1: Using tail in one terminal
tail -f mcp-app.log ui-app.log

# Option 2: Using screen sessions (preferred)
screen -r mcp-app    # Attach to MCP app session
# Ctrl+A, D to detach

screen -r ui-app     # Attach to UI app session
# Ctrl+A, D to detach
```

#### Filter Logs by Level
```bash
# Show only errors and warnings
tail -f mcp-app.log | grep -E "ERROR|WARNING"

# Show INFO level and above
tail -f mcp-app.log | grep -E "INFO|WARNING|ERROR"

# Highlight errors in color
tail -f mcp-app.log | grep --color=always -E "ERROR|WARNING|$"
```

#### Search Historical Logs
```bash
# Search for specific term
grep "optimization_runs" mcp-app.log

# Search with context (5 lines before and after)
grep -C 5 "Failed" mcp-app.log

# Count occurrences
grep -c "HTTP/1.1\" 200" mcp-app.log
```

### Stopping Local Apps

```bash
# Stop all apps
./stop-all-apps.sh

# Or manually kill screen sessions
screen -X -S mcp-app quit
screen -X -S ui-app quit
```

---

## Databricks Deployment Logging

### App Names in Databricks
- **MCP App**: `range-opt-mcp-daveok`
- **UI App**: `range-opt-ui-daveok`

These are defined in `databricks.yml`:

```yaml
resources:
  apps:
    range_optimizer_mcp:
      name: range-opt-mcp-daveok
    range_optimizer_ui:
      name: range-opt-ui-daveok
```

### Streaming Databricks Logs

#### Follow MCP App Logs in Real-Time
```bash
databricks apps logs range-opt-mcp-daveok --follow
```

#### Follow UI App Logs in Real-Time
```bash
databricks apps logs range-opt-ui-daveok --follow
```

#### View Last N Lines
```bash
# View last 100 lines
databricks apps logs range-opt-mcp-daveok --tail 100

# View last 500 lines and follow
databricks apps logs range-opt-mcp-daveok --tail 500 --follow
```

#### Filter Databricks Logs
```bash
# Pipe to grep for filtering
databricks apps logs range-opt-mcp-daveok --follow | grep ERROR

# Highlight specific terms
databricks apps logs range-opt-mcp-daveok --follow | grep --color=always -E "ERROR|WARNING|$"
```

### Check App Status

```bash
# Get app details and status
databricks apps get range-opt-mcp-daveok

# List all apps
databricks apps list

# Get app URL
databricks apps get range-opt-mcp-daveok --output json | jq -r '.url'
```

---

## Monitoring Both Environments Simultaneously

### Use Multiple Terminal Windows/Tabs

**Terminal 1 - Local MCP Logs:**
```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp
tail -f mcp-app.log
```

**Terminal 2 - Local UI Logs:**
```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp
tail -f ui-app.log
```

**Terminal 3 - Databricks MCP Logs:**
```bash
databricks apps logs range-opt-mcp-daveok --follow
```

**Terminal 4 - Databricks UI Logs:**
```bash
databricks apps logs range-opt-ui-daveok --follow
```

### Using tmux for Split Screen Monitoring

```bash
# Create new tmux session
tmux new -s logs

# Split horizontally (Ctrl+B, ")
# Split vertically (Ctrl+B, %)
# Navigate panes (Ctrl+B, arrow keys)

# In each pane, run one of:
tail -f mcp-app.log
tail -f ui-app.log
databricks apps logs range-opt-mcp-daveok --follow
databricks apps logs range-opt-ui-daveok --follow
```

---

## Log Levels and Format

### Application Log Format

Logs use structured format with timestamp, app name, level, and module:

```
2026-01-12 10:10:32.780 | excel-writeback | INFO     | tools.log            | [MCP] ✓ Registered 9 MCP tools
2026-01-12 10:11:00.789 | excel-writeback | INFO     | m.get_optimization_r | Found 15 optimization runs
2026-01-12 10:13:35.362 | excel-writeback | ERROR    | database.connect     | Connection failed
```

### Log Levels

- **INFO**: Normal operational messages
- **WARNING**: Warning messages, app continues
- **ERROR**: Error messages, operation failed
- **DEBUG**: Detailed debugging information (dev mode only)

### Key Log Patterns to Monitor

#### Database Operations
```bash
tail -f mcp-app.log | grep "database\|pool\|connect"
```

#### API Requests
```bash
tail -f mcp-app.log | grep "GET\|POST\|PUT\|DELETE\|HTTP"
```

#### MCP Tool Executions
```bash
tail -f mcp-app.log | grep "\[MCP\]"
```

#### Optimization Runs
```bash
tail -f mcp-app.log | grep "optimization"
```

#### Errors and Warnings
```bash
tail -f mcp-app.log | grep -E "ERROR|WARNING"
```

---

## Deployment Workflow with Logging

### 1. Deploy to Databricks
```bash
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-lakebase-mcp

# Deploy apps
databricks bundle deploy
```

### 2. Monitor Deployment Logs
```bash
# In separate terminals, monitor each app
databricks apps logs range-opt-mcp-daveok --follow
databricks apps logs range-opt-ui-daveok --follow
```

### 3. Test Locally While Monitoring Production
```bash
# Terminal 1: Start local apps
./start-all-apps.sh --dev

# Terminal 2: Monitor local MCP
tail -f mcp-app.log

# Terminal 3: Monitor production MCP
databricks apps logs range-opt-mcp-daveok --follow
```

---

## Common Log Scenarios

### Scenario 1: Debugging Database Connection Issues

**Local:**
```bash
tail -f mcp-app.log | grep -E "database|pool|connect|PGHOST|PGUSER"
```

**Databricks:**
```bash
databricks apps logs range-opt-mcp-daveok --follow | grep -E "database|pool|connect"
```

### Scenario 2: Tracking API Performance

```bash
# Local - see response times
tail -f mcp-app.log | grep "HTTP/1.1"

# Databricks
databricks apps logs range-opt-mcp-daveok --follow | grep "HTTP"
```

### Scenario 3: Monitoring Optimization Runs

```bash
# Local
tail -f mcp-app.log | grep -E "optimization_runs|OPT-"

# Databricks
databricks apps logs range-opt-mcp-daveok --follow | grep "optimization"
```

### Scenario 4: Watching Hot Reload Activity

```bash
# Only relevant for local development
tail -f mcp-app.log | grep -E "WatchFiles|Reloading|Shutting down"
```

---

## Troubleshooting

### Local Logs Not Appearing

```bash
# Check if apps are running
screen -ls

# Check if log files exist
ls -lh mcp-app.log ui-app.log

# Restart apps
./stop-all-apps.sh
./start-all-apps.sh --dev
```

### Databricks Logs Not Streaming

```bash
# Verify app is deployed
databricks apps list | grep range-opt

# Check app status
databricks apps get range-opt-mcp-daveok

# Verify authentication
databricks auth env

# Try without --follow first
databricks apps logs range-opt-mcp-daveok --tail 50
```

### Log Files Growing Too Large

```bash
# Check log file sizes
ls -lh *.log

# Archive old logs
mv mcp-app.log mcp-app.log.$(date +%Y%m%d_%H%M%S)
mv ui-app.log ui-app.log.$(date +%Y%m%d_%H%M%S)

# Restart apps to create fresh logs
./stop-all-apps.sh
./start-all-apps.sh
```

### Connection to Databricks Times Out

```bash
# Check network connectivity
curl -I https://adb-7405614596482958.18.azuredatabricks.net

# Verify Databricks CLI authentication
databricks auth login --host https://adb-7405614596482958.18.azuredatabricks.net

# Check if VPN is required for your workspace
```

---

## Log Rotation and Cleanup

### Local Development

The local log files are **not automatically rotated**. Recommended cleanup:

```bash
# Clean logs before starting fresh session
./stop-all-apps.sh
rm -f mcp-app.log ui-app.log
./start-all-apps.sh --dev
```

### Archive Old Logs

```bash
# Create logs directory
mkdir -p logs/archive

# Archive with timestamp
mv mcp-app.log logs/archive/mcp-app-$(date +%Y%m%d_%H%M%S).log
mv ui-app.log logs/archive/ui-app-$(date +%Y%m%d_%H%M%S).log
```

### Automated Cleanup Script

```bash
# Add to your .gitignore
echo "*.log" >> .gitignore
echo "logs/" >> .gitignore

# Optional: Create cleanup script
cat > cleanup-logs.sh << 'EOF'
#!/bin/bash
# Archive and clean logs older than 7 days
mkdir -p logs/archive
find . -name "*.log" -maxdepth 1 -mtime +7 -exec mv {} logs/archive/ \;
find logs/archive -name "*.log" -mtime +30 -delete
EOF
chmod +x cleanup-logs.sh
```

---

## Best Practices

### ✅ Do's

1. **Use `--dev` flag during development** for hot reload and verbose logging
2. **Monitor logs in separate terminals** to catch issues early
3. **Filter logs by relevance** using grep to reduce noise
4. **Archive logs periodically** to prevent disk space issues
5. **Use structured log searches** with grep patterns for debugging
6. **Monitor both apps** (MCP and UI) when troubleshooting
7. **Keep logs in .gitignore** to prevent committing large log files

### ❌ Don'ts

1. **Don't commit log files** to git (add `*.log` to `.gitignore`)
2. **Don't run both local and Databricks apps on same ports**
3. **Don't ignore WARNING messages** - they often precede errors
4. **Don't tail logs without filtering** on high-traffic apps (too much noise)
5. **Don't assume local behavior matches Databricks** - always verify in both

---

## Quick Reference Commands

### Local Development
```bash
# Start apps
./start-all-apps.sh --dev

# View logs
tail -f mcp-app.log                           # Stream MCP logs
tail -f ui-app.log                            # Stream UI logs
tail -f mcp-app.log | grep ERROR              # Filter errors
tail -n 100 -f mcp-app.log                    # Last 100 lines + follow

# Stop apps
./stop-all-apps.sh

# Screen management
screen -ls                                    # List sessions
screen -r mcp-app                             # Attach to MCP session
# Ctrl+A, D to detach
```

### Databricks Deployment
```bash
# Stream logs
databricks apps logs range-opt-mcp-daveok --follow
databricks apps logs range-opt-ui-daveok --follow

# View recent logs
databricks apps logs range-opt-mcp-daveok --tail 100

# Check status
databricks apps get range-opt-mcp-daveok
databricks apps list

# Deploy
databricks bundle deploy
```

### Combined Monitoring
```bash
# Terminal 1: Local MCP
tail -f mcp-app.log | grep --color=always -E "ERROR|WARNING|$"

# Terminal 2: Databricks MCP
databricks apps logs range-opt-mcp-daveok --follow | grep ERROR
```

---

## Related Documentation

- [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md) - Local development setup
- [DEPLOYMENT.md](./notebooks/DEPLOYMENT.md) - Databricks deployment guide
- [README.md](./README.md) - Project overview

---

## Support

If you encounter logging issues:

1. **Check app status**: Verify apps are running (`screen -ls` locally or `databricks apps list`)
2. **Verify authentication**: Ensure Databricks CLI is authenticated
3. **Review error messages**: Check both stdout and stderr in logs
4. **Check network**: Ensure connectivity to Databricks workspace
5. **Consult docs**: Reference [Databricks Apps documentation](https://docs.databricks.com/dev-tools/databricks-apps.html)

---

**Last Updated**: January 12, 2026  
**Maintainer**: David O'Keeffe (david.okeeffe@databricks.com)
