#!/bin/bash
cd /Workspace/Users/david.okeeffe@databricks.com/range_optimizer_sync/mcp_app
exec /local_disk0/.ephemeral_nfs/cluster_libraries/python/bin/python -c 'import sys; sys.path.insert(0, "/Workspace/Users/david.okeeffe@databricks.com/range_optimizer_sync/mcp_app"); from range_optimizer.backend.mcp.server import mcp_server; mcp_server.run()'
