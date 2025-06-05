import base64
import io
import datetime
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union

import pandas as pd
import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, clientside_callback, callback_context

from ..config.unity_catalog import get_full_table_name
from ..config.workspace_client import get_connection
from .tables import (
    insert_overwrite_table,
    read_table,
    check_table_exists,
    initialize_table,
)
from ..components.input import (
    CSV_TO_GRID_COL_MAP,
    get_null_description,
)


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


# 1. Initialize store on load
@callback(
    Output("grid-data-store", "data"),
    Input("page-load", "id"),  # Triggers when component mounts
    State("grid-data-store", "data"),  # Check existing data
    prevent_initial_call=False,
)
def initialize_store(
    _: str, existing_data: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    log("=" * 50)
    log("CALLBACK: initialize_store")
    log(f"Triggered by: {callback_context.triggered}")
    log(f"Existing data: {len(existing_data) if existing_data else 0} records")
    log("=" * 50)

    # Always check the database on app start to ensure we have the latest data
    # You can change this behavior if you prefer to use local storage when available

    if existing_data:
        log("→ Using existing local storage data")
        return existing_data

    try:
        conn = get_connection()
        log("✓ Got database connection")

        table_name = get_full_table_name("layout_data")
        log(f"✓ Full table name: {table_name}")

        # Check if table exists, create it if it doesn't
        table_existed = check_table_exists(table_name, conn)
        log(f"✓ Table initializing with sample data: {table_existed}")

        # If table didn't exist, initialize it with sample data
        if not table_existed:
            log(f"→ Table {table_name} didn't exist, initializing with sample data")
            result = initialize_table("layout_data", conn)
            log(f"✓ Initialize table result: {result}")

        # Now read the data from the table
        query = f"SELECT * FROM {table_name} LIMIT 1"
        log(f"→ Executing query: {query}")
        data = read_table(table_name, query, conn).to_dict("records")
        log(f"✓ Read {len(data)} records from table")

        log("✓ Successfully initialized from database")
        return [] 
    except Exception as e:
        log(f"✗ Error initializing store: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

        # If we have existing data in local storage and database fails, use it
        if existing_data:
            log(
                f"→ Using existing local storage data with {len(existing_data)} records"
            )
            return existing_data

        log(f"→ Falling back to initial data")
        return []


# 2. Export CSV
@callback(
    Output("ag-grid-table", "exportDataAsCsv"),
    Input("csv-button", "n_clicks"),
)
def export_data_as_csv(n_clicks: Optional[int]) -> bool:
    log(f"CALLBACK: export_data_as_csv - n_clicks: {n_clicks}")
    if n_clicks:
        log("→ Triggering CSV export")
        return True
    return False


# 3. Upload data to UC
@callback(
    Output("submit-button", "disabled"),
    Output("null-description-box", "children", allow_duplicate=True),
    Output("data-load-overlay", "visible", allow_duplicate=True),
    Input("submit-button", "n_clicks"),
    Input("grid-data-store", "data"),
    Input("upload-data", "contents"),
    prevent_initial_call=True,
)
def upload_data_to_uc(
    n_clicks: Optional[int],
    store_data: List[Dict[str, Any]],
    upload_clicks: Optional[str],
) -> Tuple[bool, List[dmc.Alert], bool]:
    log(
        f"CALLBACK: upload_data_to_uc - n_clicks: {n_clicks}, has_upload: {upload_clicks is not None}"
    )
    log(f"Store data: {len(store_data) if store_data else 0} records")

    # Get validation alerts from the existing function
    alerts = get_null_description(store_data).children
    log(f"Current alerts: {alerts}")

    # Only disable if there are critical errors (red alerts)
    has_critical_errors = any(alert.color not in ["green"] for alert in alerts)
    log(f"Has critical errors: {has_critical_errors}")

    if has_critical_errors:
        # Disable if critical errors
        log("→ Disabling submit button due to errors")
        return True, alerts, False

    if n_clicks:
        log("→ Processing forecast submission")
        conn = get_connection()
        forecast_id = (
            f"FCST-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        )
        log(f"→ Generated forecast ID: {forecast_id}")

        df = pd.DataFrame(store_data)
        timestamp = datetime.datetime.now().isoformat()
        df["FORECAST_ID"] = forecast_id
        df["SUBMISSION_TIMESTAMP"] = timestamp
        df["ROW_ID"] = [f"{forecast_id}-{i+1:04d}" for i in range(len(df))]

        table_name = get_full_table_name("forecast_submissions")
        log(f"→ Writing to table: {table_name}")

        insert_overwrite_table(
            df=df,
            table_name=table_name,
            conn=conn,
            overwrite=False,
        )

        success_alert = dmc.Alert(
            title="Congrats - Forecast is submitted",
            color="green",
            radius="md",
            children=[
                f"Your forecast is now being processed. You will receive an email when it is ready. Forecast ID: {forecast_id}"
            ],
            style={"marginBottom": "8px"},
        )
        log("✓ Forecast submitted successfully")
        return True, [success_alert], False
    return False, alerts, False


# 4. Update null description when store changes
@callback(
    Output("null-description-box", "children", allow_duplicate=True),
    Input("grid-data-store", "data"),
    prevent_initial_call=True,
)
def update_null_desc_box(store_data: List[Dict[str, Any]]) -> dmc.Stack:
    log(
        f"CALLBACK: update_null_desc_box - {len(store_data) if store_data else 0} records"
    )
    return get_null_description(store_data)


# 5. Grid rowData from store
@callback(Output("ag-grid-table", "rowData"), Input("grid-data-store", "data"))
def update_grid_from_store(store_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    log(
        f"CALLBACK: update_grid_from_store - {len(store_data) if store_data else 0} records"
    )
    log(store_data)
    return store_data if store_data is not None else []


# 6. Handle CSV upload
@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Output("upload-data", "contents"),
    Input("upload-data", "contents"),
    State("grid-data-store", "data"),
    State("enable-overwrite", "checked"),
    prevent_initial_call=True,
)
def update_data(
    contents: Optional[str], current_data: List[Dict[str, Any]], overwrite: bool
) -> Tuple[List[Dict[str, Any]], None]:
    log(
        f"CALLBACK: update_data - has_contents: {contents is not None}, overwrite: {overwrite}"
    )
    log(f"Current data: {len(current_data) if current_data else 0} records")

    if contents is None:
        return current_data, None

    log("→ Processing CSV upload")
    _, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        log(f"→ Read CSV with {len(df)} rows, {len(df.columns)} columns")

        df = df.rename(columns=CSV_TO_GRID_COL_MAP).dropna(how="all")
        new_data = df.to_dict("records")
        log(f"→ Processed {len(new_data)} valid records")

        if overwrite:
            log("→ Overwriting existing data")
            return new_data, None
        else:
            log("→ Appending to existing data")
            return current_data + new_data, None
    except Exception as e:
        log(f"✗ Error processing CSV file: {e}")
        return current_data, None


# 7. Filter by category
@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("category-select", "value"),
    State("grid-data-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def update_grid_by_category(
    selected_category: Optional[str], current_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    log(f"CALLBACK: update_grid_by_category - category: {selected_category}")

    if not selected_category:
        log("→ No category selected, returning current data")
        return current_data

    try:
        conn = get_connection()
        table_name = get_full_table_name("layout_data")
        conditions = []
        if selected_category != "All":
            conditions.append(f"CATEGORY_NAME = '{selected_category}'")
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM {table_name} WHERE {where_clause}"
        log(f"→ Executing query: {query}")

        with conn.cursor() as cursor:
            cursor.execute(query)
            filtered = cursor.fetchall_arrow().to_pandas()

        result = filtered.to_dict("records")
        log(f"✓ Filtered to {len(result)} records")
        return result
    except Exception as e:
        log(f"✗ Error filtering data: {e}")
        return current_data


# 8. Update store on cell edit
@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("ag-grid-table", "cellValueChanged"),
    State("ag-grid-table", "rowData"),
    prevent_initial_call=True,
)
def update_store_on_cell_change(
    cell_changed: Dict[str, Any], row_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if cell_changed:
        log(f"CALLBACK: update_store_on_cell_change")
        log(f"Cell changed: {cell_changed}")
        log(f"Row data: {len(row_data) if row_data else 0} records")
    return row_data


# 9. Reset button
@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Output("category-select", "value"),
    Input("reset-button", "n_clicks"),
    prevent_initial_call=True,
)
def reset_data(_: int) -> Tuple[None, None]:
    log(f"CALLBACK: reset_data - n_clicks: {_}")
    log("→ Clearing data and category selection")
    return None, []

# 10. Delete selected rows
@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("delete-button", "n_clicks"),
    State("ag-grid-table", "selectedRows"),
    State("grid-data-store", "data"),
    prevent_initial_call=True,
)
def delete_selected_rows(_: int, selected_rows: List[Dict[str, Any]], current_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Delete selected rows from the grid data store.
    https://dash.plotly.com/dash-ag-grid/row-selection 
    """
    log(f"CALLBACK: delete_selected_rows - n_clicks: {_}")
    log(f"Selected rows: {len(selected_rows) if selected_rows else 0} records")
    
    if not selected_rows or not current_data:
        return current_data
        
    # Filter out selected rows by comparing all key-value pairs
    filtered_data = [
        row for row in current_data 
        if not any(
            all(row.get(k) == selected.get(k) for k in row.keys() & selected.keys())
            for selected in selected_rows
        )
    ]
    
    log(f"Removed {len(current_data) - len(filtered_data)} rows")
    return filtered_data



clientside_callback(
    """
    function(n_clicks) {
        return (function(n_clicks) {
            if (n_clicks === null || n_clicks === undefined) {
                return false;
            }
            const timestamp = new Date().toISOString();
            console.log(`[${timestamp}] CLIENTSIDE CALLBACK: updateLoadingState - n_clicks:`, n_clicks);
            return true;
        })(n_clicks);
    }
    """,
    Output("data-load-overlay", "visible", allow_duplicate=True),
    Input("submit-button", "n_clicks"),
    prevent_initial_call=True,
)
