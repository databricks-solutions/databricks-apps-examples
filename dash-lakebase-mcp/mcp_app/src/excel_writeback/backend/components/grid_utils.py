from typing import List, Dict, Any
import pandas as pd


def create_column_definitions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Create AG Grid column definitions from a Pandas DataFrame schema.

    Args:
        df: Pandas DataFrame to generate column definitions for

    Returns:
        List of column definition dictionaries for AG Grid
    """
    column_defs = []

    for column in df.columns:
        # Get the data type of the column
        dtype = df[column].dtype

        # Create base column definition
        col_def = {
            "field": column,
            "headerName": column.replace("_", " ").title(),
            "filter": True,
            "sortable": True,
        }

        # Add type-specific configurations
        if pd.api.types.is_numeric_dtype(dtype):
            col_def.update(
                {
                    "type": "numericColumn",
                    "filter": "agNumberColumnFilter",
                    "valueFormatter": {"function": "d3.format(',.2f')"},
                }
            )
        elif pd.api.types.is_datetime64_dtype(dtype):
            col_def.update(
                {
                    "type": "dateColumn",
                    "filter": "agDateColumnFilter",
                    "valueFormatter": {"function": "d3.timeFormat('%Y-%m-%d')"},
                }
            )
        elif pd.api.types.is_bool_dtype(dtype):
            col_def.update(
                {
                    "type": "booleanColumn",
                    "filter": "agSetColumnFilter",
                }
            )
        else:
            col_def.update(
                {
                    "type": "textColumn",
                    "filter": "agTextColumnFilter",
                }
            )

        column_defs.append(col_def)

    return column_defs
