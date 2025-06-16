import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from excel_like_dash.components.grid_utils import create_column_definitions


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame with various data types"""
    return pd.DataFrame(
        {
            "numeric_int": [1, 2, 3],
            "numeric_float": [1.1, 2.2, 3.3],
            "text": ["a", "b", "c"],
            "snake_case_text": ["test_1", "test_2", "test_3"],
            "date": pd.date_range("2024-01-01", periods=3),
            "boolean": [True, False, True],
            "null_values": [None, "value", None],
        }
    )


def test_create_column_definitions_basic(sample_dataframe):
    """Test basic functionality of create_column_definitions"""
    column_defs = create_column_definitions(sample_dataframe)

    # Check that we have the correct number of columns
    assert len(column_defs) == len(sample_dataframe.columns)

    # Check that all columns have required base properties
    for col_def in column_defs:
        assert "field" in col_def
        assert "headerName" in col_def
        assert "filter" in col_def
        assert "sortable" in col_def


def test_numeric_column_definitions(sample_dataframe):
    """Test numeric column definitions"""
    column_defs = create_column_definitions(sample_dataframe)

    # Find numeric columns
    numeric_cols = [
        col for col in column_defs if col["field"] in ["numeric_int", "numeric_float"]
    ]

    for col in numeric_cols:
        assert col["type"] == "numericColumn"
        assert col["filter"] == "agNumberColumnFilter"
        assert "valueFormatter" in col
        assert col["valueFormatter"]["function"] == "d3.format(',.2f')"


def test_date_column_definitions(sample_dataframe):
    """Test date column definitions"""
    column_defs = create_column_definitions(sample_dataframe)

    # Find date column
    date_col = next(col for col in column_defs if col["field"] == "date")

    assert date_col["type"] == "dateColumn"
    assert date_col["filter"] == "agDateColumnFilter"
    assert "valueFormatter" in date_col
    assert date_col["valueFormatter"]["function"] == "d3.timeFormat('%Y-%m-%d')"


def test_boolean_column_definitions(sample_dataframe):
    """Test boolean column definitions"""
    column_defs = create_column_definitions(sample_dataframe)

    # Find boolean column
    bool_col = next(col for col in column_defs if col["field"] == "boolean")

    assert bool_col["type"] == "booleanColumn"
    assert bool_col["filter"] == "agSetColumnFilter"


def test_text_column_definitions(sample_dataframe):
    """Test text column definitions"""
    column_defs = create_column_definitions(sample_dataframe)

    # Find text columns
    text_cols = [
        col
        for col in column_defs
        if col["field"] in ["text", "snake_case_text", "null_values"]
    ]

    for col in text_cols:
        assert col["type"] == "textColumn"
        assert col["filter"] == "agTextColumnFilter"


def test_header_name_formatting(sample_dataframe):
    """Test that header names are properly formatted"""
    column_defs = create_column_definitions(sample_dataframe)

    # Check snake_case conversion
    snake_case_col = next(
        col for col in column_defs if col["field"] == "snake_case_text"
    )
    assert snake_case_col["headerName"] == "Snake Case Text"


def test_empty_dataframe():
    """Test handling of empty DataFrame"""
    empty_df = pd.DataFrame()
    column_defs = create_column_definitions(empty_df)
    assert len(column_defs) == 0


def test_single_column_dataframe():
    """Test handling of DataFrame with single column"""
    single_col_df = pd.DataFrame({"test": [1, 2, 3]})
    column_defs = create_column_definitions(single_col_df)

    assert len(column_defs) == 1
    assert column_defs[0]["field"] == "test"
    assert column_defs[0]["type"] == "numericColumn"
