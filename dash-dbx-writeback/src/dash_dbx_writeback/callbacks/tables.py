import pandas as pd
import datetime

from databricks import sql
from functools import lru_cache
from typing import List, Dict, Union, Tuple, Any

from ..data.sample_product_data import INITIAL_DATA
from ..config.unity_catalog import get_full_table_name


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
        conn: Databricks connection

    Returns:
        Union[int, Tuple[str, int]]: Row count or error tuple
    """
    log(f"→ initialize_table: Starting initialization for '{table_name}'")
    df = pd.DataFrame(INITIAL_DATA)
    log(f"→ initialize_table: Created DataFrame with {len(df)} rows")

    full_table_name = get_full_table_name(table_name)
    log(f"→ initialize_table: Full table name: {full_table_name}")

    result = insert_overwrite_table(
        table_name=full_table_name, df=df, conn=conn, overwrite=True
    )
    log(f"→ initialize_table: Insert result: {result}")
    assert result == -1 or result > 0
    return result


def read_table(table_name: str, query: str, conn: Any) -> pd.DataFrame:
    log(f"→ read_table: Reading from '{table_name}'")
    log(f"→ read_table: Query: {query}")
    with conn.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall_arrow().to_pandas()
        log(f"→ read_table: Retrieved {len(result)} rows")
        return result


def check_table_exists(table_name: str, conn: Any) -> bool:
    """
    Check if a table exists in the catalog.

    Args:
        table_name: Name of the target table (format: catalog.schema.table)
        conn: Databricks connection

    Returns:
        bool: True if table exists, False otherwise
    """
    log(f"→ check_table_exists: Checking '{table_name}'")

    # Parse the table name
    parts = table_name.split(".")
    if len(parts) != 3:
        raise ValueError("Table name must be in format: catalog.schema.table")
    catalog_name, schema_name, table_name = parts
    log(
        f"→ check_table_exists: Catalog: {catalog_name}, Schema: {schema_name}, Table: {table_name}"
    )

    with conn.cursor() as cursor:
        # Check if table exists
        check_query = f"""
        SELECT 1 
        FROM {catalog_name}.information_schema.tables 
        WHERE table_schema = '{schema_name}' 
        AND table_name = '{table_name}'
        """
        log(f"→ check_table_exists: Executing query")
        cursor.execute(check_query)
        exists = cursor.fetchone() is not None
        log(f"→ check_table_exists: Table exists: {exists}")
        return exists


def create_table(table_name: str, df: pd.DataFrame, conn: Any) -> Any:
    """
    Create a table with schema based on DataFrame columns.

    Args:
        table_name: Name of the target table (format: catalog.schema.table)
        df: DataFrame containing the data to determine schema
        conn: Databricks connection
    """
    log(f"→ create_table: Creating table '{table_name}'")

    # Parse the table name
    parts = table_name.split(".")
    if len(parts) != 3:
        raise ValueError("Table name must be in format: catalog.schema.table")
    catalog_name, schema_name, table_name = parts

    with conn.cursor() as cursor:
        # Get column names and types from DataFrame
        columns = []
        for col, dtype in df.dtypes.items():
            # Map pandas dtypes to SQL types
            if dtype == "int64":
                sql_type = "BIGINT"
            elif dtype == "float64":
                sql_type = "DOUBLE"
            elif dtype == "bool":
                sql_type = "BOOLEAN"
            else:
                sql_type = "STRING"
            columns.append(f"`{col}` {sql_type}")
            log(f"→ create_table: Column '{col}' -> {sql_type}")

        # Create table with proper schema
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {catalog_name}.{schema_name}.{table_name} (
            {', '.join(columns)}
        )
        """
        log(f"→ create_table: Executing CREATE TABLE query")
        result = cursor.execute(create_query)
        log(f"→ create_table: Table created successfully")
        return result


def ensure_table_exists(table_name: str, df: pd.DataFrame, conn: Any) -> bool:
    """
    Check if table exists and create it if it doesn't.

    Args:
        table_name: Name of the target table (format: catalog.schema.table)
        df: DataFrame containing the data to write
        conn: Databricks connection

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
    Insert or overwrite data in a Databricks table.

    Args:
        table_name: Name of the target table (format: catalog.schema.table)
        df: DataFrame containing the data to write
        conn: Databricks connection
        overwrite: Whether to overwrite existing data (True) or append (False)

    Returns:
        tuple: (message: str, rowcount: int)
    """
    log(f"→ insert_overwrite_table: Starting insert to '{table_name}'")
    log(f"→ insert_overwrite_table: DataFrame shape: {df.shape}")
    log(f"→ insert_overwrite_table: Overwrite mode: {overwrite}")

    try:
        # Ensure table exists with proper schema
        ensure_table_exists(table_name, df, conn)

        with conn.cursor() as cursor:
            # Convert DataFrame to list of dictionaries for better NULL handling
            records = df.replace({pd.NA: None}).to_dict("records")
            log(f"→ insert_overwrite_table: Processing {len(records)} records")

            # Get column names
            columns = df.columns.tolist()
            columns_str = ", ".join([f"`{col}`" for col in columns])

            # Build the INSERT statement
            values_clauses = []
            for i, record in enumerate(records):
                # Handle each value, converting None to NULL
                values = []
                for col in columns:
                    val = record[col]
                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, (int, float)):
                        values.append(str(val))
                    elif isinstance(val, bool):
                        values.append(str(val).upper())
                    else:
                        # Escape single quotes and wrap in quotes
                        escaped_val = str(val).replace("'", "''")
                        values.append(f"'{escaped_val}'")
                values_clauses.append(f"({', '.join(values)})")

                if i == 0:
                    log(
                        f"→ insert_overwrite_table: Sample record values: {values[:5]}..."
                    )

            if overwrite:
                log(f"→ insert_overwrite_table: Truncating table before insert")
                cursor.execute(f"TRUNCATE TABLE {table_name}")
            else:
                log(f"→ insert_overwrite_table: Appending to existing data")

            # Combine all values into a single INSERT statement
            insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES {', '.join(values_clauses)}"
            log(
                f"→ insert_overwrite_table: Executing INSERT with {len(values_clauses)} value clauses"
            )

            # Execute the query and verify success
            cursor.execute(insert_query)
            rowcount = cursor.rowcount
            log(f"→ insert_overwrite_table: Successfully inserted {rowcount} rows")
            return rowcount

    except Exception as e:
        error_msg = f"Failed to write table: {str(e)}"
        log(f"✗ insert_overwrite_table: {error_msg}")
        return error_msg, 0
