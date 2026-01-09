"""
Database operations for Lakebase PostgreSQL with OAuth authentication.

This module provides async-compatible database operations using psycopg3
with connection pooling and automatic OAuth token rotation.
"""

import pandas as pd
import datetime
import uuid
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

from databricks.sdk import WorkspaceClient
import psycopg
from psycopg_pool import ConnectionPool

from .config import db_config
from .logger import logger


# Global connection pool
_connection_pool: Optional[ConnectionPool] = None
_workspace_client: Optional[WorkspaceClient] = None
_pool_lock = threading.Lock()


def get_workspace_client() -> WorkspaceClient:
    """Get or create Databricks workspace client"""
    global _workspace_client
    if _workspace_client is None:
        _workspace_client = WorkspaceClient()
        logger.info("Initialized Databricks workspace client")
    return _workspace_client


class RotatingTokenConnection(psycopg.Connection):
    """
    psycopg3 Connection that injects a fresh OAuth token as the password.
    Enables secure authentication with Databricks Lakebase PostgreSQL.
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
            logger.info("Initializing Databricks Lakebase connection pool")
            
            host = db_config.host
            database = db_config.database
            user = db_config.user
            instance_name = db_config.instance_name
            
            if not host:
                raise ValueError("Database host not configured")
            if not instance_name:
                raise ValueError("Instance name not configured")
            
            logger.info(f"  Host: {host}")
            logger.info(f"  Port: {db_config.pg_port}")
            logger.info(f"  Database: {database}")
            logger.info(f"  User: {user}")
            logger.info(f"  Instance: {instance_name}")
            
            def check_connection(conn: psycopg.Connection) -> None:
                """Validate connection is still alive before returning from pool"""
                try:
                    conn.execute("SELECT 1")
                except Exception:
                    raise  # Let the pool discard this connection
            
            _connection_pool = ConnectionPool(
                conninfo=f"host={host} port={db_config.pg_port} dbname={database} user={user} sslmode={db_config.pg_sslmode}",
                connection_class=RotatingTokenConnection,
                kwargs={"_instance_name": instance_name},
                min_size=db_config.pool_min_size,
                max_size=db_config.pool_max_size,
                timeout=db_config.pool_timeout,
                max_idle=300.0,  # Close connections idle for more than 5 minutes
                check=check_connection,  # Validate connections before returning
                open=True,
            )
            
            logger.info("Connection pool initialized with OAuth authentication")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            return False


def get_connection_pool() -> Optional[ConnectionPool]:
    """Get the connection pool, initializing if needed"""
    if _connection_pool is None:
        if not initialize_connection_pool():
            return None
    return _connection_pool


@contextmanager
def get_connection():
    """Context manager for getting a database connection"""
    pool = get_connection_pool()
    if pool is None:
        raise RuntimeError("Database connection pool not available")
    
    with pool.connection() as conn:
        yield conn


def close_all_connections():
    """Close all connections in the pool"""
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool is not None:
            try:
                _connection_pool.close()
                logger.info("Closed all database connections")
            except Exception as e:
                logger.error(f"Error closing connections: {e}")
            finally:
                _connection_pool = None


# ============================================================
# Query Functions
# ============================================================

def query_df(sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """Execute a query and return results as DataFrame"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return pd.DataFrame()
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        logger.debug(f"Query returned {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return pd.DataFrame()


def query_dict_list(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Execute a query and return results as list of dicts"""
    df = query_df(sql, params)
    return df.to_dict('records') if not df.empty else []


def execute_sql(sql: str, params: Optional[tuple] = None) -> bool:
    """Execute SQL statement (INSERT, UPDATE, DELETE)"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        logger.debug("SQL executed successfully")
        return True
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        return False


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists"""
    parts = table_name.split(".")
    if len(parts) == 2:
        schema_name, table_name_only = parts
    else:
        schema_name = db_config.schema_name
        table_name_only = parts[0]
    
    query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = %s
        )
    """
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (schema_name, table_name_only))
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Error checking table existence: {e}")
        return False


def create_table_from_dataframe(table_name: str, df: pd.DataFrame) -> bool:
    """Create a table with schema based on DataFrame columns"""
    columns = []
    for col, dtype in df.dtypes.items():
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
    
    create_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(columns)}
    )
    """
    
    return execute_sql(create_query)


def bulk_insert(table_name: str, df: pd.DataFrame, overwrite: bool = False) -> int:
    """Bulk insert data into a table"""
    try:
        # Ensure table exists
        if not check_table_exists(table_name):
            if not create_table_from_dataframe(table_name, df):
                raise RuntimeError("Failed to create table")
        
        columns = df.columns.tolist()
        columns_str = ", ".join([f'"{col}"' for col in columns])
        records = df.replace({pd.NA: None}).to_records(index=False)
        data = [tuple(row) for row in records]
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                if overwrite:
                    cur.execute(f"TRUNCATE TABLE {table_name}")
                
                placeholders = ", ".join(["%s"] * len(columns))
                insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                cur.executemany(insert_query, data)
            conn.commit()
        
        logger.info(f"Successfully inserted {len(data)} rows into {table_name}")
        return len(data)
        
    except Exception as e:
        logger.error(f"Failed to bulk insert: {e}")
        raise


def read_table(table_name: str, limit: Optional[int] = None) -> pd.DataFrame:
    """Read all data from a table"""
    query = f"SELECT * FROM {table_name}"
    if limit:
        query += f" LIMIT {limit}"
    return query_df(query)

