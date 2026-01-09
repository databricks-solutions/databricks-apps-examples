"""
Utility functions for Databricks authentication and database connections.

This module provides helpers for:
- Databricks WorkspaceClient authentication
- PostgreSQL database connections via Lakebase (with OAuth token rotation)
"""

import contextvars
import os
import uuid
from typing import Optional

import psycopg
from databricks.sdk import WorkspaceClient

# Context variable to store request headers (for user authentication)
header_store = contextvars.ContextVar("header_store")

# Database configuration - matches the Dash app settings
LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "daveok")
LAKEBASE_DATABASE = os.environ.get("LAKEBASE_DATABASE", "databricks_postgres")
LAKEBASE_SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "excel_app")

# Global workspace client
_workspace_client: Optional[WorkspaceClient] = None


def log(message: str) -> None:
    """Print a log message with timestamp"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [MCP-UTILS] {message}")


def get_workspace_client() -> WorkspaceClient:
    """
    Get a WorkspaceClient authenticated as the service principal.
    
    When deployed as a Databricks App, this uses the app's service principal.
    When running locally, uses the developer's configured authentication.
    """
    global _workspace_client
    if _workspace_client is None:
        _workspace_client = WorkspaceClient()
        log("✓ Initialized Databricks workspace client")
    return _workspace_client


def get_user_authenticated_workspace_client() -> WorkspaceClient:
    """
    Get a WorkspaceClient authenticated as the end user.
    """
    is_databricks_app = "DATABRICKS_APP_NAME" in os.environ

    if not is_databricks_app:
        return WorkspaceClient()

    headers = header_store.get({})
    token = headers.get("x-forwarded-access-token")

    if not token:
        raise ValueError(
            "Authentication token not found in request headers (x-forwarded-access-token)."
        )

    return WorkspaceClient(token=token, auth_type="pat")


def get_database_config() -> dict:
    """
    Get database connection configuration.
    
    Returns host, port, database, user, and instance_name from environment
    or by querying the Databricks workspace.
    """
    # Check if already configured via environment (Databricks Apps)
    if os.environ.get("PGHOST"):
        return {
            "host": os.environ["PGHOST"],
            "port": os.environ.get("PGPORT", "5432"),
            "database": os.environ.get("PGDATABASE", LAKEBASE_DATABASE),
            "user": os.environ.get("PGUSER", ""),
            "instance_name": LAKEBASE_INSTANCE_NAME,
        }
    
    # Otherwise, look up from Lakebase instance
    w = get_workspace_client()
    instance = w.database.get_database_instance(name=LAKEBASE_INSTANCE_NAME)
    user = w.current_user.me().user_name
    
    return {
        "host": instance.read_write_dns,
        "port": "5432",
        "database": LAKEBASE_DATABASE,
        "user": user,
        "instance_name": LAKEBASE_INSTANCE_NAME,
    }


def get_oauth_token(instance_name: str) -> str:
    """
    Generate a fresh OAuth token for PostgreSQL authentication.
    
    Uses Databricks database credential generation for secure Lakebase access.
    """
    w = get_workspace_client()
    
    # Generate fresh OAuth token for PostgreSQL
    credential = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[instance_name]
    )
    
    return credential.token


def get_db_connection() -> psycopg.Connection:
    """
    Get a PostgreSQL connection to Lakebase with OAuth authentication.
    
    Creates a new connection using a fresh OAuth token.
    """
    config = get_database_config()
    
    log(f"→ Connecting to {config['host']}:{config['port']}/{config['database']}")
    
    # Get fresh OAuth token
    token = get_oauth_token(config["instance_name"])
    
    # Set search_path to the schema
    conn = psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["database"],
        user=config["user"],
        password=token,
        sslmode="require",
        options=f"-c search_path={LAKEBASE_SCHEMA}"
    )
    
    log(f"✓ Connected as {config['user']}")
    return conn


def execute_query(query: str, params: Optional[tuple] = None) -> list[dict]:
    """
    Execute a SQL query and return results as a list of dicts.
    
    Args:
        query: SQL query string
        params: Optional query parameters
        
    Returns:
        list[dict]: Query results as list of dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()  # Commit the transaction (important for DDL)
            if cur.description is None:
                return []
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def batch_insert(table_name: str, records: list[dict], overwrite: bool = False) -> int:
    """
    Batch insert records into a table.
    
    Args:
        table_name: Target table (can be schema.table)
        records: List of dictionaries mapping column names to values
        overwrite: If True, truncate table before insert
        
    Returns:
        int: Number of rows inserted
    """
    if not records:
        return 0
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if overwrite:
                log(f"  Truncating {table_name}")
                cur.execute(f"TRUNCATE TABLE {table_name}")
            
            if not records:
                return 0
                
            columns = list(records[0].keys())
            columns_str = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join(["%s"] * len(columns))
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            
            # Prepare data
            data = [tuple(r[c] for c in columns) for r in records]
            
            cur.executemany(query, data)
        conn.commit()
        log(f"✓ Inserted {len(records)} rows into {table_name}")
        return len(records)
    except Exception as e:
        log(f"✗ Error in batch_insert: {e}")
        raise
    finally:
        conn.close()
