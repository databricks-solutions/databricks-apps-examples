import datetime
from typing import List, Dict, Any

import pandas as pd
import dash_mantine_components as dmc
from dash import Input, Output, callback

from ..config.workspace_client import get_connection
from ..config.unity_catalog import get_full_table_name


def log(message: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


@callback(
    Output("results-forecast-select", "data"),
    Input("results-page-load", "id"),  # Trigger on page load
    prevent_initial_call=False,
)
def populate_forecast_dropdown(_: str):
    log("CALLBACK: populate_forecast_dropdown")
    try:
        conn = get_connection()
        table_name = get_full_table_name("forecast_submissions")
        query = f"SELECT DISTINCT FORECAST_ID FROM {table_name} ORDER BY SUBMISSION_TIMESTAMP DESC LIMIT 50"
        with conn.cursor() as cursor:
            cursor.execute(query)
            forecast_ids = [row[0] for row in cursor.fetchall()]
        return [{"value": fid, "label": fid} for fid in forecast_ids]
    except Exception as e:
        log(f"Error fetching forecast IDs: {e}")
        return []


@callback(
    Output("results-data-store", "data"),
    Output("results-description-box", "children"),
    Input("results-forecast-select", "value"),
    prevent_initial_call=True,
)
def load_forecast_results(forecast_id: str):
    log(f"CALLBACK: load_forecast_results - forecast_id: {forecast_id}")
    if not forecast_id:
        return [], "Select a forecast run to view results."
    try:
        conn = get_connection()
        table_name = get_full_table_name("forecast_results")
        query = f"SELECT * FROM {table_name} WHERE FORECAST_ID = '{forecast_id}'"
        with conn.cursor() as cursor:
            cursor.execute(query)
            df = cursor.fetchall_arrow().to_pandas()
        data = df.to_dict("records")
        msg = dmc.Text(f"Loaded {len(data)} rows for forecast {forecast_id}")
        return data, msg
    except Exception as e:
        log(f"Error loading forecast results: {e}")
        return [], dmc.Text("Error loading results.")


@callback(
    Output("results-grid", "rowData"),
    Input("results-data-store", "data"),
)
def update_grid(row_data: List[Dict[str, Any]]):
    log(f"CALLBACK: update_grid - rows: {len(row_data) if row_data else 0}")
    return row_data or []


@callback(
    Output("results-grid", "exportDataAsCsv"),
    Input("results-csv-button", "n_clicks"),
)
def export_results_csv(n_clicks):
    log(f"CALLBACK: export_results_csv - n_clicks: {n_clicks}")
    if n_clicks:
        return True
    return False 