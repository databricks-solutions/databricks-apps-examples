"""
File upload functionality for PostgreSQL backend.

Note: This replaces the Databricks Volume upload functionality.
Files are now uploaded directly to PostgreSQL tables.
"""

from typing import List, Optional, Union, Tuple
from dash import Dash, html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import os
import io
import base64
import dash
import pandas as pd

from ..database import get_connection_pool
from ..config import db_config


def get_connection():
    """Get connection pool for database operations"""
    return get_connection_pool()
from .tables import insert_overwrite_table


def layout() -> html.Div:
    return html.Div(
        [
            html.H1("Upload Data to Database"),
            dcc.Upload(
                id="upload-data",
                children=html.Div(["Drag and Drop or ", html.A("Select Files")]),
                style={
                    "width": "100%",
                    "height": "60px",
                    "lineHeight": "60px",
                    "borderWidth": "1px",
                    "borderStyle": "dashed",
                    "borderRadius": "5px",
                    "textAlign": "center",
                    "margin": "10px",
                },
                multiple=True,
            ),
            html.Div(id="output-data-upload"),
        ]
    )


@callback(
    Output("output-data-upload", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    State("upload-data", "last_modified"),
)
def update_output(
    contents: Optional[Union[str, List[str]]],
    filenames: Optional[Union[str, List[str]]],
    last_modified: Optional[Union[int, List[int]]],
) -> Union[html.Div, List[html.Div]]:
    if contents is None:
        return html.Div(
            [
                html.H5("No file uploaded yet"),
                html.P("Please upload a CSV file to begin."),
            ]
        )

    if not isinstance(filenames, list):
        filenames = [filenames]

    children = []
    for content, filename in zip(contents, filenames):
        if not filename.endswith(".csv"):
            children.append(
                html.Div(
                    [f"Error: {filename} is not a CSV file. Please upload a CSV file."]
                )
            )
            continue

        content_type, content_string = content.split(",")
        decoded = base64.b64decode(content_string)

        try:
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
            children.append(
                html.Div(
                    [
                        html.H5(f"File: {filename}"),
                        html.H6(f"Number of rows: {len(df)}"),
                        html.H6(f"Number of columns: {len(df.columns)}"),
                        html.Button(
                            "Upload to Database",
                            id="upload-to-database",
                            n_clicks=0,
                        ),
                        html.Div(id="upload-status"),
                    ]
                )
            )
        except Exception as e:
            children.append(html.Div([f"Error processing {filename}: {str(e)}"]))

    return children


@callback(
    Output("upload-status", "children"),
    Input("upload-to-database", "n_clicks"),
    State("upload-data", "contents"),
    prevent_initial_call=True,
)
def upload_to_database(
    n_clicks: int, contents: Optional[List[str]]
) -> Union[str, html.Div]:
    if n_clicks == 0:
        return ""

    if contents is None:
        return html.Div("No file to upload")

    content_type, content_string = contents[0].split(",")
    decoded = base64.b64decode(content_string)

    try:
        # Read the CSV file
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))

        # Get connection
        conn = get_connection()

        # Upload to PostgreSQL table - using a generic "uploads" table name
        # You can customize this to use a specific table name
        table_name = db_config.get_full_table_name("uploads")
        rowcount = insert_overwrite_table(
            table_name=table_name, df=df, conn=conn, overwrite=False
        )

        return html.Div(
            [
                html.P(f"Successfully uploaded {len(df)} rows to {table_name}"),
                html.P(f"Row count: {rowcount}"),
            ]
        )

    except Exception as e:
        return html.Div(f"Error uploading to database: {str(e)}")


# Simple callback to show filename
@callback(
    Output("selected-filename", "children"),
    Input("upload-data", "filename"),
    prevent_initial_call=True,
)
def update_filename(filename: Optional[str]) -> str:
    if filename:
        return filename
    return ""


# Make layout available at module level
__all__ = ["layout"]
