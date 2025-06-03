"""
Workspace client configuration.

This module provides configured Databricks workspace client and SQL connection instances.
"""

from databricks.sdk.core import Config
from databricks.sdk import WorkspaceClient
from databricks import sql
from functools import lru_cache
import os
import threading
import datetime
from typing import Optional
from contextlib import contextmanager


# Thread-local storage for connections
_thread_local = threading.local()

# Connection cache with timestamp
_connection_cache = {
    "connection": None,
    "created_at": None,
    "max_age_seconds": 3600,  # 1 hour
}
_cache_lock = threading.Lock()


@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    """
    Get a configured Databricks workspace client.

    Returns:
        WorkspaceClient: A configured Databricks workspace client instance
    """
    cfg = Config()
    return WorkspaceClient(config=cfg)


def get_connection(http_path: str = None):
    """
    Get a configured Databricks SQL connection with connection pooling.

    This function maintains a single connection that is reused across calls.
    The connection is automatically refreshed if it's older than max_age_seconds.

    Args:
        http_path: The HTTP path for the SQL warehouse. If not provided, will use DATABRICKS_HTTP_PATH env var.

    Returns:
        Connection: A configured Databricks SQL connection instance
    """
    assert os.getenv(
        "DATABRICKS_WAREHOUSE_ID"
    ), "DATABRICKS_WAREHOUSE_ID environment variable must be set"

    with _cache_lock:
        # Check if we have a valid cached connection
        if _connection_cache["connection"] is not None:
            # Check if connection is still fresh
            if _connection_cache["created_at"] is not None:
                age = (
                    datetime.datetime.now() - _connection_cache["created_at"]
                ).total_seconds()
                if age < _connection_cache["max_age_seconds"]:
                    try:
                        # Test if connection is still alive
                        with _connection_cache["connection"].cursor() as cursor:
                            cursor.execute("SELECT 1")
                        return _connection_cache["connection"]
                    except Exception:
                        # Connection is dead, will create a new one
                        print(
                            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] Connection test failed, creating new connection"
                        )
                        pass

        # Create new connection
        print(
            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] Creating new database connection"
        )
        cfg = Config()

        # Close old connection if exists
        if _connection_cache["connection"] is not None:
            try:
                _connection_cache["connection"].close()
            except Exception:
                pass

        # Create new connection
        connection = sql.connect(
            server_hostname=cfg.host,
            http_path=f"/sql/1.0/warehouses/{cfg.warehouse_id}",
            credentials_provider=lambda: cfg.authenticate,
        )

        # Update cache
        _connection_cache["connection"] = connection
        _connection_cache["created_at"] = datetime.datetime.now()

        return connection


def close_connection():
    """
    Explicitly close the cached connection.
    Useful for cleanup or when you want to force a new connection on next use.
    """
    with _cache_lock:
        if _connection_cache["connection"] is not None:
            try:
                _connection_cache["connection"].close()
                print(
                    f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] Closed database connection"
                )
            except Exception as e:
                print(
                    f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] Error closing connection: {e}"
                )
            finally:
                _connection_cache["connection"] = None
                _connection_cache["created_at"] = None


@contextmanager
def get_connection_context(http_path: str = None):
    """
    Context manager for database connections.

    This ensures proper connection handling and can be used with 'with' statements.
    The connection is NOT closed after use to allow reuse.

    Example:
        with get_connection_context() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM table")
    """
    conn = get_connection(http_path)
    try:
        yield conn
    except Exception as e:
        # Log the error but don't close the connection
        print(
            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] Error during connection use: {e}"
        )
        raise
    # Note: We don't close the connection here to allow reuse
