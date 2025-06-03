from typing import List, Optional, Union, Tuple
from dash import Dash, html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import SecurableType
import os
import io
import base64
import dash
import pandas as pd
from ..config.workspace_client import get_workspace_client
from ..config.unity_catalog import get_full_table_name
from .tables import insert_overwrite_table, get_connection

from ..config.unity_catalog import get_volume_path


def upload_file_to_volume(file_path: str, volume_path: str) -> None:
    w = get_workspace_client()

    # Read file into bytes
    with open("local_file.csv", "rb") as f:
        file_bytes = f.read()
    binary_data = io.BytesIO(file_bytes)

    # Specify volume path and upload
    volume_file_path = get_volume_path("to_ragemaker")
    w.files.upload(volume_file_path, binary_data, overwrite=True)


def check_upload_permissions(volume_name: str) -> str:
    """Check if user has required permissions on the volume"""
    try:
        volume = w.volumes.read(name=volume_name)
        current_user = w.current_user.me()
        grants = w.grants.get_effective(
            securable_type=SecurableType.VOLUME,
            full_name=volume.full_name,
            principal=current_user.user_name,
        )

        if not grants or not grants.privilege_assignments:
            return "Insufficient permissions: No grants found."

        for assignment in grants.privilege_assignments:
            for privilege in assignment.privileges:
                if privilege.privilege.value in ["ALL_PRIVILEGES", "WRITE_VOLUME"]:
                    return "Volume and permissions validated"

        return "Insufficient permissions: Required privileges not found."
    except Exception as e:
        return f"Error: {e}"


def layout() -> html.Div:
    return html.Div(
        [
            html.H1("Upload Data to Databricks"),
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
                            "Upload to Databricks",
                            id="upload-to-databricks",
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
    Input("upload-to-databricks", "n_clicks"),
    State("upload-data", "contents"),
    prevent_initial_call=True,
)
def upload_to_databricks(
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

        # Get the HTTP path from environment variable
        http_path = os.getenv("DATABRICKS_HTTP_PATH")
        if not http_path:
            return html.Div("Error: DATABRICKS_HTTP_PATH environment variable not set")

        # Get connection
        conn = get_connection(http_path)

        # Upload to Databricks
        volume_path = get_volume_path("to_ragemaker")
        rowcount = upload_file_to_volume(file_path=df, volume_path=volume_path)

        return html.Div(
            [
                html.P(f"Successfully uploaded {len(df)} rows to {table_name}"),
                html.P(f"Row count: {rowcount}"),
            ]
        )

    except Exception as e:
        return html.Div(f"Error uploading to Databricks: {str(e)}")


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
