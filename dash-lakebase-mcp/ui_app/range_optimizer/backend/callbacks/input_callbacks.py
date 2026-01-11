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
from dash import Input, Output, State, callback, callback_context, no_update, html

# Use MCP client for all data operations
from ..mcp_client import get_skus, save_skus, submit_optimization_run, validate_data

from ..components.input import (
    CSV_TO_GRID_COL_MAP,
    COLUMN_DEFS,
    EDITABLE_FIELDS,
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

def build_validation_summary(data: Optional[List[Dict[str, Any]]]):
    """
    Run validation via MCP API and return both the rendered alert stack and a flag
    indicating if submission should be blocked (no data or any errors).
    """
    # Check for empty data first
    if not data:
        no_data_alert = dmc.Alert(
            title="No Data",
            color="red",
            radius="md",
            children=["Please add SKU records before submitting."],
            style={"marginBottom": "8px"},
        )
        alert_stack = dmc.Stack([no_data_alert], gap="sm")
        return alert_stack, True
    
    # Call MCP validation API
    response = validate_data(data)
    
    if not response.success:
        # MCP server error - show error but allow local validation fallback
        error_alert = dmc.Alert(
            title="Validation Service Unavailable",
            color="yellow",
            radius="md",
            children=[f"Could not connect to validation service: {response.error}"],
            style={"marginBottom": "8px"},
        )
        alert_stack = dmc.Stack([error_alert], gap="sm")
        return alert_stack, False  # Don't block submission on MCP error
    
    # Parse validation results from MCP
    validation_result = response.data
    issues = validation_result.get("issues", [])
    
    # Build alerts from issues
    alerts = []
    
    # Group issues by severity
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") == "warning"]
    
    # Add error alerts (red)
    if errors:
        error_messages = []
        for error in errors[:5]:  # Show first 5 errors
            msg = error.get("message", "Unknown error")
            if error.get("sell_id"):
                msg = f"SKU {error['sell_id']}: {msg}"
            error_messages.append(msg)
        
        if len(errors) > 5:
            error_messages.append(f"... and {len(errors) - 5} more errors")
        
        alerts.append(dmc.Alert(
            title=f"❌ {len(errors)} Error(s) Found",
            color="red",
            radius="md",
            children=[html.Div([html.Div(msg) for msg in error_messages])],
            style={"marginBottom": "8px"},
        ))
    
    # Add warning alerts (yellow)
    if warnings:
        warning_messages = []
        for warning in warnings[:3]:  # Show first 3 warnings
            msg = warning.get("message", "Unknown warning")
            if warning.get("sell_id"):
                msg = f"SKU {warning['sell_id']}: {msg}"
            warning_messages.append(msg)
        
        if len(warnings) > 3:
            warning_messages.append(f"... and {len(warnings) - 3} more warnings")
        
        alerts.append(dmc.Alert(
            title=f"⚠️ {len(warnings)} Warning(s)",
            color="yellow",
            radius="md",
            children=[html.Div([html.Div(msg) for msg in warning_messages])],
            style={"marginBottom": "8px"},
        ))
    
    # Add success alert if no issues
    if not errors and not warnings:
        alerts.append(dmc.Alert(
            title="✓ Validation Passed",
            color="green",
            radius="md",
            children=[validation_result.get("summary", f"{len(data)} SKU records are ready for submission.")],
            style={"marginBottom": "8px"},
        ))
    
    alert_stack = dmc.Stack(alerts, gap="sm") if alerts else dmc.Stack([], gap="sm")
    disable_submit = validation_result.get("has_errors", False)
    
    return alert_stack, disable_submit


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
def validate_grid(store_data: List[Dict[str, Any]]) -> Tuple[bool, dmc.Stack]:
    """Validate grid data and toggle submit button."""
    alert_stack, disable_submit = build_validation_summary(store_data)
    log(f"VALIDATION: disable_submit={disable_submit}")
    return disable_submit, alert_stack


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
        (Output("submit-button", "disabled"), True, False),
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
    _, has_critical_errors = build_validation_summary(data_for_validation)
    
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
        # Make all EDITABLE_FIELDS editable
        if field in EDITABLE_FIELDS:
            col["editable"] = True
        
        # Special handling for STATUS dropdown
        if field == "STATUS":
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
    State("grid-data-store", "data"),  # Use store data, not grid rowData (which can be stale)
    prevent_initial_call=True,
)
def update_store_on_cell_change(
    cell_changed: Dict[str, Any], store_data: List[Dict[str, Any]]
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

    if not cell_changed or not store_data:
        return store_data or []

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

    updated = store_data
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
