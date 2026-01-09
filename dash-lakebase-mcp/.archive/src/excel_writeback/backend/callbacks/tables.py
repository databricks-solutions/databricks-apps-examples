import pandas as pd
import datetime
from functools import lru_cache
from typing import List, Dict, Union, Tuple, Any

from ..sample_data import INITIAL_DATA
from ..config import db_config
from ..database import query_df, bulk_insert, check_table_exists


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def initialize_table(table_name: str, conn: Any) -> Union[int, Tuple[str, int]]:
    """
    Initialize a table with sample data. By default, this will overwrite the table with the sample data for
    the app.

    Args:
        table_name: Name of the table to initialize
        conn: PostgreSQL connection

    Returns:
        Union[int, Tuple[str, int]]: Row count or error tuple
    """
    log(f"→ initialize_table: Starting initialization for '{table_name}'")
    df = pd.DataFrame(INITIAL_DATA)
    log(f"→ initialize_table: Created DataFrame with {len(df)} rows")

    full_table_name = db_config.get_full_table_name(table_name)
    log(f"→ initialize_table: Full table name: {full_table_name}")

    result = insert_overwrite_table(
        table_name=full_table_name, df=df, conn=conn, overwrite=True
    )
    log(f"→ initialize_table: Insert result: {result}")
    assert result == -1 or result > 0
    return result


def read_table(table_name: str, query: str, conn: Any) -> pd.DataFrame:
    """
    Read data from a PostgreSQL table into a DataFrame.

    Args:
        table_name: Name of the table (not used directly, kept for API compatibility)
        query: SQL query to execute
        conn: PostgreSQL connection

    Returns:
        pd.DataFrame: Query results as a DataFrame
    """
    log(f"→ read_table: Reading from '{table_name}'")
    log(f"→ read_table: Query: {query}")
    
    try:
        # Use pandas read_sql for PostgreSQL
        result = pd.read_sql(query, conn)
        log(f"→ read_table: Retrieved {len(result)} rows")
        return result
    except Exception as e:
        log(f"✗ read_table: Error reading table: {e}")
        raise


def check_table_exists(table_name: str, conn: Any) -> bool:
    """
    Check if a table exists in the database.

    Args:
        table_name: Name of the target table (format: schema.table or just table)
        conn: PostgreSQL connection

    Returns:
        bool: True if table exists, False otherwise
    """
    log(f"→ check_table_exists: Checking '{table_name}'")

    # Parse the table name
    parts = table_name.split(".")
    if len(parts) == 2:
        schema_name, table_name_only = parts
    elif len(parts) == 1:
        schema_name = "public"
        table_name_only = parts[0]
    else:
        raise ValueError("Table name must be in format: schema.table or table")
    
    log(f"→ check_table_exists: Schema: {schema_name}, Table: {table_name_only}")

    with conn.cursor() as cursor:
        # Check if table exists using PostgreSQL information_schema
        check_query = """
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = %s
        AND table_name = %s
        """
        log(f"→ check_table_exists: Executing query")
        cursor.execute(check_query, (schema_name, table_name_only))
        exists = cursor.fetchone() is not None
        log(f"→ check_table_exists: Table exists: {exists}")
        return exists


def create_table(table_name: str, df: pd.DataFrame, conn: Any) -> Any:
    """
    Create a table with schema based on DataFrame columns.

    Args:
        table_name: Name of the target table (format: schema.table or just table)
        df: DataFrame containing the data to determine schema
        conn: PostgreSQL connection
    """
    log(f"→ create_table: Creating table '{table_name}'")

    with conn.cursor() as cursor:
        # Get column names and types from DataFrame
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
            log(f"→ create_table: Column '{col}' -> {sql_type}")

        # Create table with proper schema
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join(columns)}
        )
        """
        log(f"→ create_table: Executing CREATE TABLE query")
        cursor.execute(create_query)
        conn.commit()
        log(f"→ create_table: Table created successfully")


def ensure_table_exists(table_name: str, df: pd.DataFrame, conn: Any) -> bool:
    """
    Check if table exists and create it if it doesn't.

    Args:
        table_name: Name of the target table (format: schema.table or just table)
        df: DataFrame containing the data to write
        conn: PostgreSQL connection

    Returns:
        bool: True if table already existed, False if it was created
    """
    log(f"→ ensure_table_exists: Ensuring table '{table_name}' exists")
    table_exists = check_table_exists(table_name, conn)

    if not table_exists:
        log(f"→ ensure_table_exists: Table doesn't exist, creating it")
        create_table(table_name, df, conn)
    else:
        log(f"→ ensure_table_exists: Table already exists")

    return table_exists


def insert_overwrite_table(
    table_name: str, df: pd.DataFrame, conn: Any, overwrite: bool = True
) -> Union[int, Tuple[str, int]]:
    """
    Insert or overwrite data in a PostgreSQL table.

    Args:
        table_name: Name of the target table (format: schema.table or just table)
        df: DataFrame containing the data to write
        conn: PostgreSQL connection pool
        overwrite: Whether to overwrite existing data (True) or append (False)

    Returns:
        int: Number of rows inserted, or tuple (error_message, 0) on error
    """
    log(f"→ insert_overwrite_table: Starting insert to '{table_name}'")
    log(f"→ insert_overwrite_table: DataFrame shape: {df.shape}")
    log(f"→ insert_overwrite_table: Overwrite mode: {overwrite}")

    try:
        # Get an actual connection from the pool
        with conn.connection() as connection:
            # Ensure table exists with proper schema
            ensure_table_exists(table_name, df, connection)

            with connection.cursor() as cursor:
                # Convert DataFrame to list of tuples for insertion
                records = df.replace({pd.NA: None}).to_records(index=False)
                data = [tuple(row) for row in records]
                log(f"→ insert_overwrite_table: Processing {len(data)} records")

                # Get column names
                columns = df.columns.tolist()
                columns_str = ", ".join([f'"{col}"' for col in columns])

                if overwrite:
                    log(f"→ insert_overwrite_table: Truncating table before insert")
                    cursor.execute(f"TRUNCATE TABLE {table_name}")
                    connection.commit()
                else:
                    log(f"→ insert_overwrite_table: Appending to existing data")

                # Use executemany for efficient bulk insert
                placeholders = ", ".join(["%s"] * len(columns))
                insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                log(f"→ insert_overwrite_table: Executing bulk INSERT")

                cursor.executemany(insert_query, data)
                connection.commit()
                
                rowcount = cursor.rowcount
                log(f"→ insert_overwrite_table: Successfully inserted {rowcount} rows")
                return rowcount

    except Exception as e:
        error_msg = f"Failed to write table: {str(e)}"
        log(f"✗ insert_overwrite_table: {error_msg}")
        return error_msg, 0
