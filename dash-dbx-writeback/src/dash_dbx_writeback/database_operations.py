"""
Centralized Database Operations Module

This module provides all database operations with connection pooling
and OAuth authentication for Databricks Lakebase PostgreSQL.
"""

import pandas as pd
import datetime
import uuid
from typing import Optional, Tuple, Union
from databricks.sdk import WorkspaceClient
import psycopg
from psycopg_pool import ConnectionPool

from .config import db_config


# Global connection pool and workspace client
_connection_pool: Optional[ConnectionPool] = None
_workspace_client: Optional[WorkspaceClient] = None
_pool_lock = __import__('threading').Lock()


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def get_workspace_client() -> WorkspaceClient:
    """Get or create Databricks workspace client"""
    global _workspace_client
    if _workspace_client is None:
        _workspace_client = WorkspaceClient()
        log("✓ Initialized Databricks workspace client")
    return _workspace_client


class RotatingTokenConnection(psycopg.Connection):
    """
    psycopg3 Connection that injects a fresh OAuth token as the password.
    This enables secure authentication with Databricks Lakebase PostgreSQL.
    """
    
    @classmethod
    def connect(cls, conninfo: str = "", **kwargs):
        w = get_workspace_client()
        instance_name = kwargs.pop("_instance_name")
        
        # Generate fresh OAuth token
        token = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[instance_name]
        ).token
        
        kwargs["password"] = token
        kwargs.setdefault("sslmode", "require")
        return super().connect(conninfo, **kwargs)


def initialize_connection_pool() -> bool:
    """Initialize database connection pool with OAuth authentication"""
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool is not None:
            return True
        
        try:
            log("→ Initializing Databricks Lakebase connection pool")
            
            # Validate required environment variables are set
            if not db_config.HOST:
                raise ValueError("PGHOST not set - ensure database resource is configured")
            if not db_config.DATABASE:
                raise ValueError("PGDATABASE not set - ensure database resource is configured")
            if not db_config.USER:
                raise ValueError("PGUSER not set - ensure database resource is configured")
            
            # Get workspace client
            w = get_workspace_client()
            
            # Get instance name from config (either from LAKEBASE_INSTANCE_NAME or extracted from PGHOST)
            instance_name = db_config.INSTANCE_NAME
            if not instance_name:
                raise ValueError("INSTANCE_NAME not set - ensure database resource is configured properly")
            
            log(f"  Host: {db_config.HOST}")
            log(f"  Port: {db_config.PORT}")
            log(f"  Database: {db_config.DATABASE}")
            log(f"  User: {db_config.USER}")
            log(f"  Instance: {instance_name}")
            log(f"  SSL Mode: {db_config.SSL_MODE}")
            
            # Build connection pool with OAuth token rotation
            _connection_pool = ConnectionPool(
                conninfo=f"host={db_config.HOST} port={db_config.PORT} dbname={db_config.DATABASE} user={db_config.USER} sslmode={db_config.SSL_MODE}",
                connection_class=RotatingTokenConnection,
                kwargs={"_instance_name": instance_name},
                min_size=db_config.POOL_MIN_SIZE,
                max_size=db_config.POOL_MAX_SIZE,
                timeout=db_config.POOL_TIMEOUT,
                open=True,
            )
            
            log("✓ Lakebase connection pool initialized with OAuth authentication")
            return True
            
        except Exception as e:
            log(f"✗ Failed to initialize connection pool: {e}")
            import traceback
            traceback.print_exc()
            return False


def get_connection() -> Optional[ConnectionPool]:
    """Get the connection pool"""
    if _connection_pool is None:
        if not initialize_connection_pool():
            return None
    return _connection_pool


def close_all_connections():
    """Close all connections in the pool"""
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool is not None:
            try:
                _connection_pool.close()
                log("✓ Closed all database connections")
            except Exception as e:
                log(f"✗ Error closing connections: {e}")
            finally:
                _connection_pool = None


def query_df(sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """
    Execute a query and return results as DataFrame
    
    Args:
        sql: SQL query string
        params: Optional tuple of parameters for parameterized query
        
    Returns:
        pd.DataFrame: Query results
    """
    pool = get_connection()
    if pool is None:
        log("✗ Could not get database connection")
        return pd.DataFrame()
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return pd.DataFrame()
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        log(f"✓ Query returned {len(df)} rows")
        return df
    except Exception as e:
        log(f"✗ Error executing query: {e}")
        return pd.DataFrame()


def execute_sql(sql: str, params: Optional[tuple] = None) -> bool:
    """
    Execute SQL statement (INSERT, UPDATE, DELETE, etc.)
    
    Args:
        sql: SQL statement string
        params: Optional tuple of parameters for parameterized query
        
    Returns:
        bool: True if successful, False otherwise
    """
    pool = get_connection()
    if pool is None:
        log("✗ Could not get database connection")
        return False
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        log("✓ SQL executed successfully")
        return True
    except Exception as e:
        log(f"✗ Error executing SQL: {e}")
        return False


def check_table_exists(table_name: str) -> bool:
    """
    Check if a table exists in the database
    
    Args:
        table_name: Name of the table (schema.table or just table)
        
    Returns:
        bool: True if table exists, False otherwise
    """
    log(f"→ Checking if table '{table_name}' exists")
    
    # Parse the table name
    parts = table_name.split(".")
    if len(parts) == 2:
        schema_name, table_name_only = parts
    elif len(parts) == 1:
        schema_name = db_config.SCHEMA
        table_name_only = parts[0]
    else:
        raise ValueError("Table name must be in format: schema.table or table")
    
    query = """
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = %s
            AND table_name = %s
        )
    """
    
    pool = get_connection()
    if pool is None:
        return False
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (schema_name, table_name_only))
                exists = cur.fetchone()[0]
        log(f"✓ Table exists: {exists}")
        return exists
    except Exception as e:
        log(f"✗ Error checking table existence: {e}")
        return False


def create_table_from_dataframe(table_name: str, df: pd.DataFrame) -> bool:
    """
    Create a table with schema based on DataFrame columns
    
    Args:
        table_name: Name of the table to create
        df: DataFrame containing the data to determine schema
        
    Returns:
        bool: True if successful, False otherwise
    """
    log(f"→ Creating table '{table_name}'")
    
    columns = []
    for col, dtype in df.dtypes.items():
        # Map pandas dtypes to PostgreSQL types
        if dtype == "int64":
            sql_type = "BIGINT"
        elif dtype == "float64":
            sql_type = "DOUBLE PRECISION"
        elif dtype == "bool":
            sql_type = "BOOLEAN"
        elif dtype == "datetime64[ns]":
            sql_type = "TIMESTAMP"
        else:
            sql_type = "TEXT"
        columns.append(f'"{col}" {sql_type}')
        log(f"  Column '{col}' -> {sql_type}")
    
    create_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(columns)}
    )
    """
    
    return execute_sql(create_query)


def bulk_insert(table_name: str, df: pd.DataFrame, overwrite: bool = False) -> Union[int, Tuple[str, int]]:
    """
    Bulk insert data into a table
    
    Args:
        table_name: Name of the target table
        df: DataFrame containing the data to write
        overwrite: Whether to truncate table before insert
        
    Returns:
        int: Number of rows inserted, or tuple (error_message, 0) on error
    """
    log(f"→ Bulk inserting {len(df)} rows into '{table_name}'")
    
    pool = get_connection()
    if pool is None:
        return "Could not get database connection", 0
    
    try:
        # Ensure table exists
        if not check_table_exists(table_name):
            if not create_table_from_dataframe(table_name, df):
                return "Failed to create table", 0
        
        # Prepare data
        columns = df.columns.tolist()
        columns_str = ", ".join([f'"{col}"' for col in columns])
        records = df.replace({pd.NA: None}).to_records(index=False)
        data = [tuple(row) for row in records]
        
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Optionally truncate
                if overwrite:
                    log(f"  Truncating table before insert")
                    cur.execute(f"TRUNCATE TABLE {table_name}")
                
                # Bulk insert
                placeholders = ", ".join(["%s"] * len(columns))
                insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                cur.executemany(insert_query, data)
            conn.commit()
        
        rowcount = len(data)
        log(f"✓ Successfully inserted {rowcount} rows")
        return rowcount
            
    except Exception as e:
        error_msg = f"Failed to bulk insert: {str(e)}"
        log(f"✗ {error_msg}")
        return error_msg, 0


def read_table(table_name: str, limit: Optional[int] = None) -> pd.DataFrame:
    """
    Read all data from a table
    
    Args:
        table_name: Name of the table to read
        limit: Optional limit on number of rows
        
    Returns:
        pd.DataFrame: Table data
    """
    query = f"SELECT * FROM {table_name}"
    if limit:
        query += f" LIMIT {limit}"
    
    return query_df(query)


# Convenience functions for backward compatibility
def insert_overwrite_table(
    table_name: str, df: pd.DataFrame, conn=None, overwrite: bool = True
) -> Union[int, Tuple[str, int]]:
    """
    Legacy function for backward compatibility
    Delegates to bulk_insert (conn parameter ignored)
    """
    return bulk_insert(table_name, df, overwrite=overwrite)


def return_connection(conn):
    """Legacy function for backward compatibility - does nothing with psycopg3 pool"""
    pass


# Initialize connection pool on module import
initialize_connection_pool()
