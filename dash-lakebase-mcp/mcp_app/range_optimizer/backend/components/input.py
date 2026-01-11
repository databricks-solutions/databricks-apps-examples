from typing import List, Dict, Any, Optional

import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import html, dcc, no_update, callback, clientside_callback, register_page

from .tabs import tabs
from ..sample_data import INITIAL_DATA

EDITABLE_FIELDS = [
    "SELL_ID",
    "LOYALTY_GROUP",
    "SEGMENT_1",
    "SEGMENT_2",
    "SHELF_SPACE_CM",
]

COLUMN_DEFS = [
    {"field": "LAYOUT_ID", "headerName": "Layout ID", "filter": "agTextColumnFilter"},
    {"field": "SELL_ID", "headerName": "Sell ID", "filter": "agTextColumnFilter"},
    {
        "field": "PRODUCT_NAME",
        "headerName": "Product Name",
        "filter": "agTextColumnFilter",
    },
    {
        "field": "LOYALTY_GROUP",
        "headerName": "Loyalty Group",
        "filter": "agTextColumnFilter",
    },
    {"field": "SEGMENT_1", "headerName": "Segment 1", "filter": "agTextColumnFilter"},
    {"field": "SEGMENT_2", "headerName": "Segment 2", "filter": "agTextColumnFilter"},
    {"field": "ORIGIN", "headerName": "Origin", "filter": "agTextColumnFilter"},
    {
        "field": "CATEGORY_NAME",
        "headerName": "Category Name",
        "filter": "agTextColumnFilter",
    },
    {
        "field": "SUBCATEGORY_NAME",
        "headerName": "Subcategory Name",
        "filter": "agTextColumnFilter",
    },
    {
        "field": "ITEM_CLASS_NAME",
        "headerName": "Item Class Name",
        "filter": "agTextColumnFilter",
    },
    {"field": "SUPPLIER", "headerName": "Supplier", "filter": "agTextColumnFilter"},
    {"field": "BRAND", "headerName": "Brand", "filter": "agTextColumnFilter"},
    {"field": "PACK_SIZE", "headerName": "Pack Size", "filter": "agTextColumnFilter"},
    {
        "field": "SHELF_SPACE_CM",
        "headerName": "Shelf Space (cm)",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
    },
]

CSV_TO_GRID_COL_MAP = {
    "Layout ID": "LAYOUT_ID",
    "Sell ID": "SELL_ID",
    "Product Name": "PRODUCT_NAME",
    "Loyalty Group": "LOYALTY_GROUP",
    "Segment 1": "SEGMENT_1",
    "Segment 2": "SEGMENT_2",
    "Origin": "ORIGIN",
    "Category Name": "CATEGORY_NAME",
    "Subcategory Name": "SUBCATEGORY_NAME",
    "Item Class Name": "ITEM_CLASS_NAME",
    "Supplier": "SUPPLIER",
    "Brand": "BRAND",
    "Pack Size": "PACK_SIZE",
    "Shelf Space (cm)": "SHELF_SPACE_CM",
}


def get_null_description(data: Optional[List[Dict[str, Any]]] = None) -> dmc.Stack:
    """
    Generate validation alerts for the input data.
    
    Validates:
    - Required fields are present
    - Numeric fields are valid integers/floats
    - Categorical fields match valid options
    - Value ranges are appropriate
    """
    issues: List[str] = []
    warnings: List[str] = []
    duplicate_sell_ids: List[str] = []
    
    # Valid values for categorical fields
    VALID_LOYALTY_GROUPS = {"Gold", "Silver", "Bronze", "Standard"}
    VALID_CATEGORIES = {"Beer & Seltzer", "Hot Sauce", "Ice Cream", "Beverages", "Snacks"}
    
    if data:
        sell_id_counts: Dict[str, int] = {}
        for row in data:
            sell_id = row.get("SELL_ID")
            if sell_id:
                sell_id_counts[sell_id] = sell_id_counts.get(sell_id, 0) + 1
        duplicate_sell_ids = [sid for sid, count in sell_id_counts.items() if count > 1]

        for i, row in enumerate(data):
            row_errors = []
            row_warnings = []
            sell_id = row.get('SELL_ID', 'N/A')
            
            # 1. Check required fields are present
            missing = [field for field in EDITABLE_FIELDS if not row.get(field)]
            if missing:
                row_errors.append(f"missing {', '.join(missing)}")
            
            # 2. Validate numeric fields (SHELF_SPACE_CM must be numeric and positive)
            shelf_space = row.get("SHELF_SPACE_CM")
            if shelf_space is not None and shelf_space != "":
                if isinstance(shelf_space, str):
                    row_errors.append("Shelf Space must be a number (not text)")
                elif not isinstance(shelf_space, (int, float)):
                    row_errors.append(f"Shelf Space has invalid value: {shelf_space}")
                elif shelf_space <= 0:
                    row_errors.append(f"Shelf Space must be positive (got {shelf_space})")
            
            # 3. Validate categorical fields (dropdown values)
            loyalty_group = row.get("LOYALTY_GROUP")
            if loyalty_group and loyalty_group not in VALID_LOYALTY_GROUPS:
                row_warnings.append(f"Loyalty Group '{loyalty_group}' is not standard (expected: {', '.join(VALID_LOYALTY_GROUPS)})")
            
            category_name = row.get("CATEGORY_NAME")
            if category_name and category_name not in VALID_CATEGORIES:
                row_warnings.append(f"Category '{category_name}' is not in standard list")
            
            # 4. Validate string fields have reasonable values
            segment_1 = row.get("SEGMENT_1")
            segment_2 = row.get("SEGMENT_2")
            if segment_1 and not isinstance(segment_1, str):
                row_errors.append("Segment 1 must be text")
            if segment_2 and not isinstance(segment_2, str):
                row_errors.append("Segment 2 must be text")
            
            # Add errors and warnings to lists
            if row_errors:
                issues.append(f"Row {i+1} (SELL_ID: {sell_id}): {', '.join(row_errors)}")
            if row_warnings:
                warnings.append(f"Row {i+1} (SELL_ID: {sell_id}): {', '.join(row_warnings)}")

    alerts: List[dmc.Alert] = []
    
    # Critical errors (red alerts) - prevent submission
    if duplicate_sell_ids:
        alerts.append(
            dmc.Alert(
                title="❌ Duplicate SELL_IDs Found",
                color="red",
                radius="md",
                children=[
                    "The following SELL_IDs are duplicated. Each SELL_ID must be unique:",
                    dmc.List(
                        [dmc.ListItem(sid) for sid in duplicate_sell_ids[:10]],  # Limit display
                        size="sm",
                        mt=5,
                    ),
                    dmc.Text(f"({len(duplicate_sell_ids)} duplicates total)", size="xs", c="dimmed") if len(duplicate_sell_ids) > 10 else None,
                ],
                style={"marginBottom": "8px"},
            )
        )
    
    if issues:
        alerts.append(
            dmc.Alert(
                title="❌ Data Validation Errors",
                color="red",
                radius="md",
                children=[
                    "Fix these errors before submitting:",
                    dmc.List(
                        [dmc.ListItem(issue) for issue in issues[:15]],  # Limit display
                        size="sm",
                        mt=5,
                    ),
                    dmc.Text(f"({len(issues)} errors total)", size="xs", c="dimmed", mt=5) if len(issues) > 15 else None,
                ],
                style={"marginBottom": "8px"},
            )
        )
    
    # Warnings (yellow alerts) - allow submission but warn user
    if warnings:
        alerts.append(
            dmc.Alert(
                title="⚠️ Data Validation Warnings",
                color="yellow",
                radius="md",
                children=[
                    "These issues won't prevent submission but should be reviewed:",
                    dmc.List(
                        [dmc.ListItem(warning) for warning in warnings[:15]],  # Limit display
                        size="sm",
                        mt=5,
                    ),
                    dmc.Text(f"({len(warnings)} warnings total)", size="xs", c="dimmed", mt=5) if len(warnings) > 15 else None,
                ],
                style={"marginBottom": "8px"},
            )
        )
    
    # Success message (green alert) - all validation passed
    if not alerts and data:
        alerts.append(
            dmc.Alert(
                title="✅ Data Validated Successfully",
                color="green",
                radius="md",
                children=[
                    dmc.Text(f"All {len(data)} records passed validation checks.", size="sm"),
                    dmc.Text("You can proceed with submitting the forecast.", size="sm", fw=600, mt=5),
                ],
                style={"marginBottom": "8px"},
            )
        )
    
    # Info message (blue alert) - no data loaded yet
    if not data:
        alerts.append(
            dmc.Alert(
                title="📋 Begin by Picking Your Product Category",
                color="blue",
                radius="md",
                children="Use the dropdown above to pick your category, this will fetch a table from Databricks using SQL",
                style={"marginBottom": "8px"},
            )
        )
    
    return dmc.Stack(alerts, gap="xs")


def render_input_grid() -> html.Div:
    """
    Renders a input grid interface with a text area and a submit button.

    Returns:
        html.Div: A Div containing an AgGrid component.
    """

    # Add editable property and cellStyle for fields in EDITABLE_FIELDS
    for col in COLUMN_DEFS:
        if col["field"] in EDITABLE_FIELDS:
            col["editable"] = True
            col["cellStyle"] = {
                "styleConditions": [
                    {
                        "condition": "!params.value",
                        "style": {"backgroundColor": "#ffcccc"},
                    },
                    {"condition": "true", "style": {"backgroundColor": "#e6f3ff"}},
                ]
            }

    reset_button = dmc.Button(
        "Reset",
        variant="outline",
        color="red",
        id="reset-button",
        n_clicks=0,
    )
    download_button = dmc.Button(
        "Download CSV", variant="outline", color="red", id="csv-button", n_clicks=0
    )
    sumbit_button = dmc.Button(
        "Submit Forecast Run",
        variant="filled",
        color="red",
        id="submit-button",
        n_clicks=0,
        loading=False,
        loaderProps={"type": "dots"},
    )
    delete_button = dmc.Button(
        "Delete Rows",
        variant="outline",
        color="red",
        id="delete-button",
        n_clicks=0,
    )
    upload_button = dcc.Upload(
        id="upload-data",
        children=dmc.Button("Upload CSV", variant="outline", color="red"),
        multiple=False,
    )

    # Add a Store component to maintain the data state
    store = dcc.Store(id="grid-data-store", storage_type="local")

    # Add category dropdown to main layout
    category_dropdown = dmc.Select(
        id="category-select",
        label="Pick your category",
        data=["All", "Beer & Seltzer", "Hot Sauce", "Ice Cream"],
        searchable=True,
        value=None,
        w=400,
        persistence=True,
        persistence_type="local",
    )

    overwrite_switch = dmc.Switch(
        id="enable-overwrite",
        size="sm",
        radius="sm",
        label="Overwrite on Upload?",
        checked=True,
    )

    grid = dag.AgGrid(
        id="ag-grid-table",
        rowData=[],
        columnDefs=COLUMN_DEFS,
        columnSize="autoSize",
        className="ag-theme-quartz",
        dashGridOptions={
            "undoRedoCellEditing": True,
            "undoRedoCellEditingLimit": 20,
            "rowDragManaged": True,
            "rowDragEntireRow": True,
            "rowSelection": "multiple",
        },
        defaultColDef={
            "editable": False,
            "cellDataType": False,
            "sortable": True,
            "filter": True,
            "floatingFilter": True,
            "resizable": True,
            "minWidth": 150,
        },
        csvExportParams={
            "fileName": "layout_data.csv",
            "columnKeys": [col["field"] for col in COLUMN_DEFS],
            "skipColumnGroupHeaders": True,
        },
        rowClassRules={"ag-row-hover": "true"},
        style={"--ag-row-hover-color": "#f5f5f5"},
    )

    description_box = html.Div(
        get_null_description(data=None), id="null-description-box"
    )

    info_box = html.Div(get_null_description(data=None), id="info-box")

    data_overlay = dmc.LoadingOverlay(
        id="data-load-overlay",
        zIndex=10,
        loaderProps={
            "variant": "custom",
            "children": dmc.Stack(
                [
                    dmc.Image(
                        h=150,
                        radius="md",
                        src="/assets/dbx-logo.png",
                    ),
                    dmc.Text(
                        "Uploading Ranges to Databricks", size="xl", fw=700, c="black"
                    ),
                ]
            ),
        },
        overlayProps={"radius": "sm", "blur": 2},
        visible=False,
    )

    # Store for the submitted forecast ID
    forecast_id_store = dcc.Store(id="submitted-forecast-id", storage_type="session")
    
    # Submission progress panel with Databricks branding
    submission_progress = html.Div(
        id="submission-progress-container",
        children=[
            dmc.Paper(
                [
                    dmc.Group(
                        [
                            dmc.Image(
                                src="/assets/dbx-logo.png",
                                h=40,
                                w=40,
                                fit="contain",
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text("Processing Forecast", fw=700, size="lg"),
                                    dmc.Text(
                                        id="submission-status-text",
                                        children="Submitting to Databricks...",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                ],
                                gap=2,
                            ),
                        ],
                        gap="md",
                    ),
                    dmc.Space(h=16),
                    dmc.Progress(
                        id="submission-progress-bar",
                        value=0,
                        size="xl",
                        radius="xl",
                        striped=True,
                        animated=True,
                        color="red",
                    ),
                    dmc.Space(h=8),
                    dmc.Group(
                        [
                            dmc.Badge(
                                id="submission-step-badge",
                                children="Step 1/4",
                                color="red",
                                variant="light",
                            ),
                            dmc.Text(
                                id="submission-step-detail",
                                children="Writing forecast data...",
                                size="xs",
                                c="dimmed",
                                ff="monospace",
                            ),
                        ],
                        gap="sm",
                    ),
                ],
                p="lg",
                radius="md",
                withBorder=True,
                style={"backgroundColor": "#fff5f5", "borderColor": "#E21837"},
            ),
        ],
        style={"display": "none", "marginTop": "20px"},
    )
    
    # Navigation card that appears after submission
    results_nav_card = html.Div(
        id="results-nav-container",
        children=[
            dmc.Alert(
                id="submission-success-alert",
                title="✅ Forecast Submitted Successfully!",
                color="green",
                radius="md",
                children=[
                    dmc.Text(id="submission-forecast-id-text", size="sm"),
                    dmc.Space(h=10),
                    dmc.Group([
                        dcc.Link(
                            dmc.Button(
                                "View Results & Ask AI",
                                id="view-results-button",
                                color="red",
                                variant="filled",
                                leftSection=html.Span("🤖"),
                                size="md",
                            ),
                            href="/stock-optimization",
                            style={"textDecoration": "none"},
                        ),
                        dmc.Text("Navigate to see optimization results and ask the AI Assistant questions", size="xs", c="dimmed"),
                    ], gap="md"),
                ],
            ),
        ],
        style={"display": "none"},  # Hidden by default
    )
    
    return html.Div(
        [
            html.Div(
                id="page-load", style={"display": "none"}
            ),  # Hidden div for initialization trigger
            store,
            forecast_id_store,
            dmc.Space(h=10),
            category_dropdown,
            dmc.Space(h=10),
            data_overlay,
            description_box,
            grid,
            dmc.Space(h=10),
            dmc.Group(
                [
                    reset_button,
                    delete_button,
                    download_button,
                    upload_button,
                    sumbit_button,
                    overwrite_switch,
                ]
            ),
            # Submission progress (shown during processing)
            submission_progress,
            # Navigation to results appears after submission
            results_nav_card,
        ]
    )
