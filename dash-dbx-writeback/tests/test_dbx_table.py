import pandas as pd
import pytest
import os

from unittest.mock import Mock, patch, MagicMock
from excel_like_dash.callbacks.tables import read_table, insert_overwrite_table
from excel_like_dash.data.sample_product_data import INITIAL_DATA
from excel_like_dash.config.workspace_client import get_connection
from excel_like_dash.config.unity_catalog import get_full_table_name


@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.execute = Mock()
    cursor.fetchall_arrow = Mock()
    cursor.rowcount = -1  # Set default rowcount
    cursor.message = "Success"  # Set default message
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    connection = MagicMock()
    # Make the context manager return the mock_cursor
    context_manager = MagicMock()
    context_manager.__enter__.return_value = mock_cursor
    context_manager.__exit__.return_value = None
    connection.cursor.return_value = context_manager
    return connection


def test_read_table(mock_connection, mock_cursor):
    # Setup test data
    test_data = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    mock_cursor.fetchall_arrow.return_value.to_pandas.return_value = test_data

    # Test the read_table function
    result = read_table("test_table", mock_connection)

    # Verify the results
    assert isinstance(result, pd.DataFrame)
    assert result.equals(test_data)
    mock_cursor.execute.assert_called_once_with("SELECT * FROM test_table")


@patch("dash_dbx_writeback.config.workspace_client.get_connection")
def test_get_connection(mock_get_connection):
    # Setup
    mock_connection = MagicMock()
    mock_get_connection.return_value = mock_connection

    # Test
    result = get_connection()

    # Verify
    assert result == mock_connection
    mock_get_connection.assert_called_once()


@pytest.mark.integration
def test_real_warehouse_connection():
    """Integration test that connects to a real Databricks warehouse.

    This test requires the following environment variables to be set:
    - DATABRICKS_HOST: Your Databricks workspace URL
    - DATABRICKS_HTTP_PATH: The HTTP path of your SQL warehouse
    - DATABRICKS_TOKEN: Your Databricks access token
    - DATABRICKS_CATALOG: Your Unity Catalog catalog name
    - DATABRICKS_SCHEMA: Your Unity Catalog schema name
    """
    # Skip if environment variables are not set
    required_vars = [
        "DATABRICKS_HOST",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_TOKEN",
        "DATABRICKS_CATALOG",
        "DATABRICKS_SCHEMA",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        pytest.skip(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Test connection
    conn = get_connection()
    assert conn is not None

    # Test reading a table using the Unity Catalog configuration
    test_table = get_full_table_name("bakehouse_data")
    try:
        df = read_table(test_table, conn)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        print(f"Successfully read {len(df)} rows from {test_table}")
    except Exception as e:
        pytest.fail(f"Failed to read table: {str(e)}")


@pytest.mark.integration
def test_real_writeback():
    """Integration test that connects to a real Databricks warehouse.

    This test requires the following environment variables to be set:
    - DATABRICKS_HOST: Your Databricks workspace URL
    - DATABRICKS_HTTP_PATH: The HTTP path of your SQL warehouse
    - DATABRICKS_TOKEN: Your Databricks access token
    - DATABRICKS_CATALOG: Your Unity Catalog catalog name
    - DATABRICKS_SCHEMA: Your Unity Catalog schema name
    """
    # Skip if environment variables are not set
    required_vars = [
        "DATABRICKS_HOST",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_TOKEN",
        "DATABRICKS_CATALOG",
        "DATABRICKS_SCHEMA",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        pytest.skip(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Test connection
    conn = get_connection()
    assert conn is not None

    # Test writing to a table using the Unity Catalog configuration
    test_table = get_full_table_name("pytest_writeback")
    try:
        df = pd.DataFrame(INITIAL_DATA)
        rowcount = insert_overwrite_table(
            table_name=test_table, df=df, conn=conn, overwrite=True
        )
        # Check if rowcount is either -1 (success) or a positive number (actual count)
        assert rowcount == -1 or rowcount > 0

        result = read_table(test_table, conn)
        assert result is not None
        assert len(result) == len(df)
        # Compare only the columns that exist in both DataFrames
        common_cols = list(set(df.columns) & set(result.columns))
        assert result[common_cols].equals(df[common_cols])
        print(f"Successfully read {len(result)} rows from {test_table}")
    except Exception as e:
        pytest.fail(f"Failed to write table: {str(e)}")
