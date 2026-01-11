"""
Input callbacks for the Range Optimizer UI.

Handles:
- SKU data loading and display
- Grid editing and validation
- Range optimization submission
- CSV import/export

All data operations go through the MCP client - no direct database access!
"""

import base64
import io
import datetime
import copy
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, callback_context, no_update

# Use MCP client for all data operations
from ..mcp_client import get_skus, save_skus, submit_optimization_run

from ..components.input import (
    CSV_TO_GRID_COL_MAP,
    get_null_description,
    COLUMN_DEFS,
)


# =============================================================================
# Configuration
# =============================================================================

# Fields that require strict integer values when edited
INTEGER_FIELDS = {
    "WEEKLY_UNITS": "Weekly Units",
    "CURRENT_FACINGS": "Current Facings",
    "PACK_WIDTH_MM": "Pack Width",
}

# Fields that must match a finite set of dropdown-like options
SELECT_FIELD_OPTIONS = {
    "STATUS": {"active", "new", "discontinued"},
    "CATEGORY": {"Beer & Seltzer", "Hot Sauce", "Ice Cream"},
}

# Cache for dropdown options to avoid unnecessary re-renders
LAST_COLUMN_OPTIONS = {
    "STATUS": None,
    "CATEGORY": None,
}


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


# =============================================================================
# 1. Initialize store on load (via MCP)
# =============================================================================

@callback(
    Output("grid-data-store", "data"),
    Input("url", "pathname"),
    State("grid-data-store", "data"),
    prevent_initial_call=False,
)
def initialize_store(
    _: str, existing_data: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Load SKU data from MCP server on page load."""
    log("=" * 50)
    log("CALLBACK: initialize_store (via MCP)")
    log(f"Triggered by: {callback_context.triggered}")
    log(f"Existing data: {len(existing_data) if existing_data else 0} records")
    log("=" * 50)

    # Always load fresh data from MCP server
    response = get_skus()
    
    if response.success:
        data = response.data
        log(f"✓ Loaded {len(data)} SKUs from MCP ({response.source})")
        return data
    else:
        log(f"⚠️ MCP error: {response.error}")
        # Use existing data as fallback
        if existing_data:
            log(f"→ Using existing local data: {len(existing_data)} records")
            return existing_data
        return []


# =============================================================================
# 2. Export CSV
# =============================================================================

@callback(
    Output("ag-grid-table", "exportDataAsCsv"),
    Input("csv-button", "n_clicks"),
)
def export_data_as_csv(n_clicks: Optional[int]) -> bool:
    """Trigger CSV export from grid."""
    log(f"CALLBACK: export_data_as_csv - n_clicks: {n_clicks}")
    if n_clicks:
        log("→ Triggering CSV export")
        return True
    return False


# =============================================================================
# 3a. Live validation to toggle submit + alerts
# =============================================================================

@callback(
    Output("submit-button", "disabled"),
    Output("null-description-box", "children", allow_duplicate=True),
    Input("grid-data-store", "data"),
    prevent_initial_call=True,
)
def validate_grid(store_data: List[Dict[str, Any]]) -> Tuple[bool, List[dmc.Alert]]:
    """Validate grid data and toggle submit button."""
    alerts = get_null_description(store_data).children
    has_critical_errors = any(alert.color not in ["green"] for alert in alerts)
    return has_critical_errors, alerts


# =============================================================================
# 3b. Submit Range Optimization Run (via MCP)
# =============================================================================

@callback(
    Output("data-load-overlay", "visible"),
    Output("submitted-forecast-id", "data"),
    Output("results-nav-container", "style"),
    Output("submission-forecast-id-text", "children"),
    Output("view-results-link", "href"),
    Input("submit-button", "n_clicks"),
    State("grid-data-store", "data"),
    State("upload-data", "contents"),
    prevent_initial_call=True,
    background=True,
    running=[
        (Output("submission-progress-container", "style"), {"display": "block", "marginTop": "20px"}, {"display": "none"}),
        (Output("reset-button", "disabled"), True, False),
        (Output("delete-button", "disabled"), True, False),
        (Output("csv-button", "disabled"), True, False),
        (Output("upload-data", "disabled"), True, False),
    ],
    progress=[
        Output("submission-progress-bar", "value"),
        Output("submission-step-badge", "children"),
        Output("submission-step-detail", "children"),
        Output("submission-status-text", "children"),
    ],
)
def submit_range_optimization(
    set_progress,
    n_clicks: Optional[int],
    grid_data: List[Dict[str, Any]],
    upload_clicks: Optional[str],
) -> Tuple[bool, Optional[str], Dict, str, str]:
    """Submit optimization run via MCP server."""
    log(f"CALLBACK: submit_range_optimization - n_clicks: {n_clicks}")
    
    data_for_validation = grid_data or []
    log(f"Store data: {len(data_for_validation)} records")

    # Validate
    alerts = get_null_description(data_for_validation).children
    has_critical_errors = any(alert.color not in ["green"] for alert in alerts)
    
    hidden_style = {"display": "none"}
    visible_style = {"display": "block", "marginTop": "20px"}

    if has_critical_errors:
        log("→ Blocking submit due to validation errors")
        return False, None, hidden_style, "", "/stock-optimization"

    if n_clicks:
        log("→ Submitting optimization run via MCP...")
        
        # Step 1: Prepare data
        set_progress((20, "Step 1/4", "Preparing SKU data...", "Loading demand and margin data..."))
        import time
        time.sleep(0.3)
        
        # Step 2: Building constraints
        set_progress((40, "Step 2/4", "Building constraints...", "Setting up shelf space and brand constraints..."))
        time.sleep(0.3)
        
        # Step 3: Submit to MCP server
        set_progress((70, "Step 3/4", "Running optimization...", "Submitting to MCP server..."))
        
        response = submit_optimization_run(data_for_validation)
        
        if response.success:
            run_id = response.data.get("run_id", "unknown")
            sku_count = response.data.get("sku_count", len(data_for_validation))
            status = response.data.get("optimization_status", "unknown")
            
            log(f"✓ Optimization submitted: {run_id}, status: {status}")
            
            # Step 4: Complete
            set_progress((100, "Complete!", "Finished", "Range optimization complete!"))
            time.sleep(0.3)
            
            results_href = f"/stock-optimization?forecast={run_id}"
            return False, run_id, visible_style, f"Run ID: {run_id}", results_href
        else:
            log(f"❌ MCP error: {response.error}")
            # Still show as complete but with error info
            set_progress((100, "Complete", "Finished (with warnings)", response.error or "Check MCP server"))
            return False, None, hidden_style, "", "/stock-optimization"
    
    return False, None, hidden_style, "", "/stock-optimization"


# =============================================================================
# 5. Grid rowData from store
# =============================================================================

@callback(Output("ag-grid-table", "rowData"), Input("grid-data-store", "data"))
def update_grid_from_store(store_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update grid with data from store."""
    log(f"CALLBACK: update_grid_from_store - {len(store_data) if store_data else 0} records")
    return store_data if store_data is not None else []


# =============================================================================
# 6a. Dynamically update column definitions
# =============================================================================

@callback(
    Output("ag-grid-table", "columnDefs"),
    Input("grid-data-store", "data"),
    prevent_initial_call=False,
)
def update_column_defs(store_data: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Build column definitions with select editors from data."""
    status_options = sorted(
        {str(row.get("STATUS")) for row in (store_data or []) if row.get("STATUS")}
    ) or sorted(SELECT_FIELD_OPTIONS["STATUS"])

    category_options = sorted(
        {str(row.get("CATEGORY")) for row in (store_data or []) if row.get("CATEGORY")}
    ) or sorted(SELECT_FIELD_OPTIONS["CATEGORY"])

    # Avoid re-renders if options haven't changed
    if (
        LAST_COLUMN_OPTIONS["STATUS"] == status_options
        and LAST_COLUMN_OPTIONS["CATEGORY"] == category_options
    ):
        return no_update

    defs = copy.deepcopy(COLUMN_DEFS)

    for col in defs:
        field = col.get("field")
        if field == "STATUS":
            col["editable"] = True
            col["cellEditor"] = "agSelectCellEditor"
            col["cellEditorParams"] = {"values": status_options}
            col["filter"] = "agTextColumnFilter"
        elif field == "CATEGORY":
            col["filter"] = "agTextColumnFilter"

    LAST_COLUMN_OPTIONS["STATUS"] = status_options
    LAST_COLUMN_OPTIONS["CATEGORY"] = category_options
    return defs


# =============================================================================
# 6b. Handle CSV upload
# =============================================================================

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
    """Handle CSV file upload."""
    log(f"CALLBACK: update_data - has_contents: {contents is not None}, overwrite: {overwrite}")

    if contents is None:
        return current_data, None

    log("→ Processing CSV upload")
    _, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    
    try:
        df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        log(f"→ Read CSV: {len(df)} rows, {len(df.columns)} columns")

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
        log(f"✗ Error processing CSV: {e}")
        return current_data, None


# =============================================================================
# 7. Filter by category (via MCP)
# =============================================================================

@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("category-select", "value"),
    State("grid-data-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def update_grid_by_category(
    selected_category: Optional[str], current_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Filter data by category via MCP server."""
    log(f"CALLBACK: update_grid_by_category - category: {selected_category}")

    if not selected_category:
        return current_data

    # Call MCP server for filtered data
    response = get_skus(category=selected_category)
    
    if response.success:
        log(f"✓ Got {len(response.data)} SKUs for category: {selected_category}")
        return response.data
    else:
        log(f"⚠️ MCP error: {response.error}, using client-side filter")
        # Fallback to client-side filtering
        if selected_category == "All":
            return current_data
        return [row for row in current_data if row.get("CATEGORY") == selected_category]


# =============================================================================
# 8. Update store on cell edit
# =============================================================================

@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("ag-grid-table", "cellValueChanged"),
    State("ag-grid-table", "rowData"),
    prevent_initial_call=True,
)
def update_store_on_cell_change(
    cell_changed: Dict[str, Any], row_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Validate and update store on cell edit."""

    def coerce_int(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        if isinstance(value, float) and not value.is_integer():
            return None
        return parsed

    if not cell_changed or not row_data:
        return row_data

    def apply_change(change: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(change, dict):
            return rows

        col_id = change.get("colId")
        new_value = change.get("newValue")
        old_value = change.get("oldValue")
        row_key = change.get("data", {}).get("SKU_ID")

        updated_rows: List[Dict[str, Any]] = []

        for row in rows:
            if not isinstance(row, dict):
                updated_rows.append(row)
                continue

            if row.get("SKU_ID") != row_key:
                updated_rows.append(row)
                continue

            updated_row = row.copy()

            if col_id in INTEGER_FIELDS:
                coerced = coerce_int(new_value)
                if coerced is None:
                    log(f"✗ Invalid integer for {INTEGER_FIELDS[col_id]}: {new_value}")
                    fallback = coerce_int(old_value)
                    updated_row[col_id] = fallback if fallback is not None else old_value
                else:
                    updated_row[col_id] = coerced
            elif col_id in SELECT_FIELD_OPTIONS:
                allowed = SELECT_FIELD_OPTIONS[col_id]
                if new_value in allowed:
                    updated_row[col_id] = new_value
                else:
                    log(f"✗ Invalid option for {col_id}: {new_value}")
                    updated_row[col_id] = old_value if old_value in allowed else next(iter(allowed))
            else:
                updated_row[col_id] = new_value

            updated_rows.append(updated_row)

        return updated_rows

    changes = cell_changed if isinstance(cell_changed, list) else [cell_changed]

    log("CALLBACK: update_store_on_cell_change")
    log(f"Cell changed: {cell_changed}")

    updated = row_data
    for change in changes:
        updated = apply_change(change, updated)

    return updated


# =============================================================================
# 9. Reset button
# =============================================================================

@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Output("category-select", "value"),
    Input("reset-button", "n_clicks"),
    prevent_initial_call=True,
)
def reset_data(_: int) -> Tuple[None, None]:
    """Clear data and trigger reload."""
    log(f"CALLBACK: reset_data - n_clicks: {_}")
    return None, []


# =============================================================================
# 10. Delete selected rows
# =============================================================================

@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("delete-button", "n_clicks"),
    State("ag-grid-table", "selectedRows"),
    State("grid-data-store", "data"),
    prevent_initial_call=True,
)
def delete_selected_rows(
    _: int, selected_rows: List[Dict[str, Any]], current_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Delete selected rows from grid data."""
    log(f"CALLBACK: delete_selected_rows - {len(selected_rows) if selected_rows else 0} selected")

    if not selected_rows or not current_data:
        return current_data

    filtered_data = [
        row
        for row in current_data
        if not any(
            all(row.get(k) == selected.get(k) for k in row.keys() & selected.keys())
            for selected in selected_rows
        )
    ]

    log(f"Removed {len(current_data) - len(filtered_data)} rows")
    return filtered_data
