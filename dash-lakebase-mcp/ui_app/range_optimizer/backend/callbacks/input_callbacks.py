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
    "SEGMENT": {
        "Craft Beer", "Hard Seltzer",  # Beer & Seltzer
        "Asian Style", "Louisiana Style", "Mexican Style",  # Hot Sauce
        "Premium Pints", "Family Tubs",  # Ice Cream
    },
}

# Segment options by category (for dynamic validation)
SEGMENT_BY_CATEGORY = {
    "Beer & Seltzer": {"Craft Beer", "Hard Seltzer"},
    "Hot Sauce": {"Asian Style", "Louisiana Style", "Mexican Style"},
    "Ice Cream": {"Premium Pints", "Family Tubs"},
}

# Editable fields that have validation rules - these get highlighted
# (Integer fields OR select fields) AND editable fields
VALIDATED_EDITABLE_FIELDS = (set(INTEGER_FIELDS.keys()) | set(SELECT_FIELD_OPTIONS.keys())) & set(EDITABLE_FIELDS)

# Cache for dropdown options to avoid unnecessary re-renders
LAST_COLUMN_OPTIONS = {
    "STATUS": None,
    "CATEGORY": None,
}

def build_validation_summary(data: Optional[List[Dict[str, Any]]]) -> Tuple[dmc.Stack, bool, List[Dict[str, Any]]]:
    """
    Run validation via MCP API and return:
    1. The rendered alert stack
    2. A flag indicating if submission should be blocked (no data or any errors)
    3. The data with _errors field added to each row for cell highlighting
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
        return alert_stack, True, []
    
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
        return alert_stack, False, data  # Return original data on MCP error
    
    # Parse validation results from MCP
    validation_result = response.data
    issues = validation_result.get("issues", [])
    
    log(f"VALIDATION RESULT: valid={validation_result.get('valid')}, has_errors={validation_result.get('has_errors')}")
    log(f"VALIDATION ISSUES: {len(issues)} issues found")
    if issues:
        for issue in issues[:3]:  # Log first 3 issues
            log(f"  → Issue: {issue}")
    
    # Build error map: row_index -> {field: error_message}
    error_map: Dict[int, Dict[str, str]] = {}
    for issue in issues:
        if issue.get("severity") == "error":
            row_idx = issue.get("row_index")
            field = issue.get("field")
            message = issue.get("message", "Error")
            if row_idx is not None and field:
                if row_idx not in error_map:
                    error_map[row_idx] = {}
                error_map[row_idx][field] = message
                log(f"  → Error cell: row={row_idx}, field={field}")
    
    # Add _errors field to each row for cell styling
    # Make a copy of data to avoid mutating original
    data_with_errors = []
    for i, row in enumerate(data):
        row_copy = dict(row)
        if i in error_map:
            row_copy["_errors"] = error_map[i]
        else:
            row_copy["_errors"] = {}
        data_with_errors.append(row_copy)
    
    log(f"VALIDATION: {len(error_map)} rows have errors")
    
    # Build alerts from issues
    alerts = []
    
    # Group issues by severity
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") == "warning"]
    log(f"VALIDATION GROUPED: {len(errors)} errors, {len(warnings)} warnings")
    
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
    
    return alert_stack, disable_submit, data_with_errors


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
# 3a. Live validation to toggle submit + alerts + cell highlighting
# =============================================================================

@callback(
    Output("submit-button", "disabled"),
    Output("null-description-box", "children", allow_duplicate=True),
    Output("ag-grid-table", "rowData"),
    Input("grid-data-store", "data"),
    prevent_initial_call="initial_duplicate",  # Run on initial load AND allow duplicates
)
def validate_grid(store_data: List[Dict[str, Any]]) -> Tuple[bool, dmc.Stack, List[Dict[str, Any]]]:
    """Validate grid data, toggle submit button, and update grid with error highlighting."""
    alert_stack, disable_submit, data_with_errors = build_validation_summary(store_data)
    log(f"VALIDATION: disable_submit={disable_submit}, rows_with_errors={sum(1 for r in (data_with_errors or []) if r.get('_errors'))}")
    return disable_submit, alert_stack, data_with_errors


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

    # Validate (ignore data_with_errors for submit)
    _, has_critical_errors, _ = build_validation_summary(data_for_validation)
    
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
# 5. Grid rowData from store - REMOVED
# =============================================================================
# NOTE: Removed update_grid_from_store - validate_grid now handles updating
# the grid with validation error highlighting


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
    log(f"CALLBACK: update_column_defs - store has {len(store_data) if store_data else 0} records")
    log(f"  EDITABLE_FIELDS = {EDITABLE_FIELDS}")
    
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
        log("  → Returning no_update (options unchanged)")
        return no_update

    log(f"  → Building new column defs with status_options={status_options}")
    defs = copy.deepcopy(COLUMN_DEFS)

    # Fields that get validation-aware styling using styleConditions
    VALIDATED_FIELDS = {"WEEKLY_UNITS", "UNIT_PRICE", "UNIT_COST", "CURRENT_FACINGS", 
                        "PACK_WIDTH_MM", "STATUS", "SEGMENT"}
    
    # Error style for cells with validation errors (red)
    ERROR_STYLE = {
        "backgroundColor": "rgba(239, 68, 68, 0.20)",
        "borderLeft": "4px solid #ef4444",
        "color": "#991b1b"
    }
    
    # Style for editable numeric fields (light blue)
    NUMERIC_EDIT_STYLE = {
        "backgroundColor": "rgba(59, 130, 246, 0.08)",
        "borderLeft": "3px solid #3b82f6"
    }
    
    # Style for editable dropdown fields (light purple)
    SELECT_EDIT_STYLE = {
        "backgroundColor": "rgba(139, 92, 246, 0.08)",
        "borderLeft": "3px solid #8b5cf6"
    }
    
    editable_cols = []
    for col in defs:
        field = col.get("field")
        # Make all EDITABLE_FIELDS editable
        if field in EDITABLE_FIELDS:
            col["editable"] = True
            editable_cols.append(field)
        
        # Apply validation-aware styling using styleConditions (built-in AG Grid feature)
        # This avoids custom JS functions and uses AG Grid's native condition syntax
        if field in VALIDATED_FIELDS:
            # Build field-specific condition checking _errors object
            error_condition = f"params.data && params.data._errors && params.data._errors.{field}"
            
            style_conditions = [
                # Error style takes priority (checked first)
                {"condition": error_condition, "style": ERROR_STYLE}
            ]
            
            # Add field-type specific default styling
            if field in {"WEEKLY_UNITS", "UNIT_PRICE", "UNIT_COST", "CURRENT_FACINGS", "PACK_WIDTH_MM"}:
                # For numeric fields, use blue styling when no error
                style_conditions.append({
                    "condition": f"!({error_condition})",
                    "style": NUMERIC_EDIT_STYLE
                })
            elif field in {"STATUS", "SEGMENT"}:
                # For dropdown fields, use purple styling when no error
                style_conditions.append({
                    "condition": f"!({error_condition})",
                    "style": SELECT_EDIT_STYLE
                })
            
            col["cellStyle"] = {"styleConditions": style_conditions}
        
        # Special handling for STATUS dropdown (static options)
        if field == "STATUS":
            col["cellEditor"] = "agSelectCellEditor"
            col["cellEditorParams"] = {"values": status_options}
            col["filter"] = "agTextColumnFilter"
        # SEGMENT uses dynamic options based on CATEGORY
        elif field == "SEGMENT":
            col["cellEditor"] = "agSelectCellEditor"
            col["cellEditorParams"] = {"function": "dynamicSegmentOptions(params)"}
            col["filter"] = "agTextColumnFilter"
        elif field == "CATEGORY":
            col["filter"] = "agTextColumnFilter"

    log(f"  → Made columns editable: {editable_cols}")
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
    selected_category: Optional[str], current_data: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Filter data by category via MCP server."""
    log(f"CALLBACK: update_grid_by_category - category: {selected_category}")

    if not selected_category:
        return current_data or []

    # Call MCP server for filtered data
    response = get_skus(category=selected_category)
    
    if response.success:
        log(f"✓ Got {len(response.data)} SKUs for category: {selected_category}")
        return response.data
    else:
        log(f"⚠️ MCP error: {response.error}, using client-side filter")
        # Fallback to client-side filtering - handle None case
        if not current_data:
            return []
        if selected_category == "All":
            return current_data
        return [row for row in current_data if row.get("CATEGORY") == selected_category]


# =============================================================================
# 8. Update store on cell edit
# =============================================================================

@callback(
    Output("grid-data-store", "data", allow_duplicate=True),
    Input("ag-grid-table", "cellValueChanged"),
    State("ag-grid-table", "rowData"),  # Grid already has updated data after edit
    prevent_initial_call=True,
)
def update_store_on_cell_change(
    cell_changed: Any, row_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Sync grid edits to the store.
    
    Per https://dash.plotly.com/dash-ag-grid/editing-and-callbacks:
    - cellValueChanged fires AFTER the grid updates its internal rowData
    - We just need to sync that updated rowData to the store
    
    cellValueChanged can be:
    - A single dict: {rowIndex, rowId, data, oldValue, newValue, colId}
    - A list of dicts (for multiple changes)
    """
    if cell_changed:
        log("=" * 60)
        log("CALLBACK: update_store_on_cell_change - CELL EDITED")
        # Handle both single change (dict) and multiple changes (list)
        changes = cell_changed if isinstance(cell_changed, list) else [cell_changed]
        for change in changes:
            if isinstance(change, dict):
                col_id = change.get('colId', '?')
                old_val = change.get('oldValue')
                new_val = change.get('newValue')
                row_idx = change.get('rowIndex', '?')
                sku_id = change.get('data', {}).get('SKU_ID', '?')
                
                log(f"  📝 EDIT: SKU={sku_id}, Column={col_id}")
                log(f"     Row: {row_idx}")
                log(f"     Old value: {repr(old_val)} (type: {type(old_val).__name__})")
                log(f"     New value: {repr(new_val)} (type: {type(new_val).__name__})")
        log(f"  → Syncing {len(row_data) if row_data else 0} records to store")
        log("=" * 60)
    else:
        log("CALLBACK: update_store_on_cell_change - cell_changed is None/empty")
    
    # The grid has already updated its rowData - just sync to store
    return row_data if row_data else []


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
