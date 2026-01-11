from typing import List, Dict, Any, Optional

import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import html, dcc

from ..sample_data import INITIAL_DATA

# Fields that users can edit for Range Optimization input
EDITABLE_FIELDS = [
    "WEEKLY_UNITS",
    "UNIT_PRICE",
    "UNIT_COST",
    "CURRENT_FACINGS",
    "IS_MUST_STOCK",
    "STATUS",
]

# Column definitions for Range Optimizer SKU grid
COLUMN_DEFS = [
    {"field": "SKU_ID", "headerName": "SKU ID", "filter": "agTextColumnFilter", "pinned": "left", "width": 100},
    {"field": "SKU_NAME", "headerName": "Product Name", "filter": "agTextColumnFilter", "width": 220},
    {"field": "BRAND", "headerName": "Brand", "filter": "agTextColumnFilter", "width": 120},
    {"field": "SEGMENT", "headerName": "Segment", "filter": "agTextColumnFilter", "width": 120},
    {"field": "PACK_SIZE", "headerName": "Pack Size", "filter": "agTextColumnFilter", "width": 100},
    {"field": "PACK_WIDTH_MM", "headerName": "Width (mm)", "filter": "agNumberColumnFilter", "type": "numericColumn", "width": 110},
    {
        "field": "WEEKLY_UNITS",
        "headerName": "Weekly Units",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 120,
    },
    {
        "field": "UNIT_PRICE",
        "headerName": "Price ($)",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 100,
        "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
    },
    {
        "field": "UNIT_COST",
        "headerName": "Cost ($)",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 100,
        "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
    },
    {
        "field": "GROSS_MARGIN_PCT",
        "headerName": "Margin %",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 100,
        "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
    },
    {
        "field": "CURRENT_FACINGS",
        "headerName": "Current Facings",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 130,
    },
    {
        "field": "IS_PRIVATE_LABEL",
        "headerName": "Private Label",
        "filter": "agTextColumnFilter",
        "width": 120,
        "cellRenderer": "agCheckboxCellRenderer",
    },
    {
        "field": "IS_MUST_STOCK",
        "headerName": "Must Stock",
        "filter": "agTextColumnFilter",
        "width": 110,
        "cellRenderer": "agCheckboxCellRenderer",
    },
    {"field": "STATUS", "headerName": "Status", "filter": "agTextColumnFilter", "width": 100},
]

CSV_TO_GRID_COL_MAP = {
    "SKU ID": "SKU_ID",
    "Product Name": "SKU_NAME",
    "Brand": "BRAND",
    "Category": "CATEGORY",
    "Segment": "SEGMENT",
    "Pack Size": "PACK_SIZE",
    "Width (mm)": "PACK_WIDTH_MM",
    "Weekly Units": "WEEKLY_UNITS",
    "Price ($)": "UNIT_PRICE",
    "Cost ($)": "UNIT_COST",
    "Margin %": "GROSS_MARGIN_PCT",
    "Current Facings": "CURRENT_FACINGS",
    "Private Label": "IS_PRIVATE_LABEL",
    "Must Stock": "IS_MUST_STOCK",
    "Status": "STATUS",
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
    duplicate_sku_ids: List[str] = []
    
    # Valid values for categorical fields
    VALID_STATUSES = {"active", "new", "discontinued"}
    VALID_CATEGORIES = {"Beer & Seltzer", "Hot Sauce", "Ice Cream"}
    
    if data:
        sku_id_counts: Dict[str, int] = {}
        for row in data:
            sku_id = row.get("SKU_ID")
            if sku_id:
                sku_id_counts[sku_id] = sku_id_counts.get(sku_id, 0) + 1
        duplicate_sku_ids = [sid for sid, count in sku_id_counts.items() if count > 1]

        for i, row in enumerate(data):
            row_errors = []
            row_warnings = []
            sku_id = row.get('SKU_ID', 'N/A')
            
            # 1. Check required fields are present
            if not row.get("WEEKLY_UNITS") and row.get("WEEKLY_UNITS") != 0:
                row_errors.append("missing Weekly Units")
            if not row.get("CURRENT_FACINGS") and row.get("CURRENT_FACINGS") != 0:
                row_errors.append("missing Current Facings")
            
            # 2. Validate integer fields (must be integers, not strings)
            integer_fields = {
                "WEEKLY_UNITS": "Weekly Units",
                "CURRENT_FACINGS": "Current Facings",
                "PACK_WIDTH_MM": "Pack Width"
            }
            
            for field, label in integer_fields.items():
                value = row.get(field)
                if value is not None and value != "":
                    # Check if it's a string that looks like a number
                    if isinstance(value, str):
                        row_errors.append(f"{label} must be a number (not text)")
                    # Check if it's a valid integer
                    elif not isinstance(value, int):
                        try:
                            int_val = int(value)
                            if int_val != value:  # e.g., 5.5 != 5
                                row_errors.append(f"{label} must be a whole number (got {value})")
                        except (ValueError, TypeError):
                            row_errors.append(f"{label} has invalid value: {value}")
                    # Check if it's positive
                    elif value < 0:
                        row_errors.append(f"{label} must be positive (got {value})")
            
            # 3. Validate float fields (must be numeric, positive)
            float_fields = {
                "UNIT_PRICE": "Unit Price",
                "UNIT_COST": "Unit Cost",
                "GROSS_MARGIN_PCT": "Margin %"
            }
            
            for field, label in float_fields.items():
                value = row.get(field)
                if value is not None and value != "":
                    if isinstance(value, str):
                        row_errors.append(f"{label} must be a number (not text)")
                    elif not isinstance(value, (int, float)):
                        row_errors.append(f"{label} has invalid value: {value}")
                    elif value <= 0:
                        row_errors.append(f"{label} must be greater than zero (got {value})")
            
            # 4. Validate boolean fields
            if "IS_MUST_STOCK" in row:
                value = row.get("IS_MUST_STOCK")
                if value is not None and not isinstance(value, bool):
                    # Accept common string representations
                    if isinstance(value, str) and value.lower() not in ["true", "false", "yes", "no", "1", "0"]:
                        row_errors.append(f"Must Stock must be Yes/No (got {value})")
            
            # 5. Validate categorical fields (dropdown values)
            if "STATUS" in row:
                status = row.get("STATUS")
                if status and status not in VALID_STATUSES:
                    row_warnings.append(f"Status '{status}' is not standard (expected: {', '.join(VALID_STATUSES)})")
            
            if "CATEGORY" in row:
                category = row.get("CATEGORY")
                if category and category not in VALID_CATEGORIES:
                    row_warnings.append(f"Category '{category}' is not in standard list")
            
            # 6. Business logic validations
            unit_price = row.get("UNIT_PRICE")
            unit_cost = row.get("UNIT_COST")
            if unit_price is not None and unit_cost is not None:
                if isinstance(unit_price, (int, float)) and isinstance(unit_cost, (int, float)):
                    if unit_cost > unit_price:
                        row_warnings.append(f"Cost (${unit_cost}) exceeds Price (${unit_price})")
            
            # Add errors and warnings to lists
            if row_errors:
                issues.append(f"Row {i+1} (SKU: {sku_id}): {', '.join(row_errors)}")
            if row_warnings:
                warnings.append(f"Row {i+1} (SKU: {sku_id}): {', '.join(row_warnings)}")

    alerts: List[dmc.Alert] = []
    
    # Critical errors (red alerts) - prevent submission
    if duplicate_sku_ids:
        alerts.append(
            dmc.Alert(
                title="❌ Duplicate SKU IDs Found",
                color="red",
                radius="md",
                children=[
                    "The following SKU IDs are duplicated. Each SKU must be unique:",
                    dmc.List(
                        [dmc.ListItem(sid) for sid in duplicate_sku_ids[:10]],  # Limit display
                        size="sm",
                        mt=5,
                    ),
                    dmc.Text(f"({len(duplicate_sku_ids)} duplicates total)", size="xs", c="dimmed") if len(duplicate_sku_ids) > 10 else None,
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
                title="✅ SKU Data Validated Successfully",
                color="green",
                radius="md",
                children=[
                    dmc.Text(f"All {len(data)} SKUs passed validation checks.", size="sm"),
                    dmc.Text("You can now run the Range Optimization.", size="sm", fw=600, mt=5),
                ],
                style={"marginBottom": "8px"},
            )
        )
    
    # Info message (blue alert) - no data loaded yet
    if not data:
        alerts.append(
            dmc.Alert(
                title="📋 Select a Product Category to Begin",
                color="blue",
                radius="md",
                children="Use the dropdown above to pick a category. This will load SKU data from Databricks for range optimization.",
                style={"marginBottom": "8px"},
            )
        )
    
    return dmc.Stack(alerts, gap="xs")


def render_input_grid() -> html.Div:
    """
    Renders the Range Optimizer input grid interface.
    
    This grid allows users to:
    - View and edit SKU data (demand, pricing, facings)
    - Set must-stock constraints
    - Submit data for range optimization

    Returns:
        html.Div: A Div containing the Range Optimizer input components.
    """

    # Add editable property and cellStyle for fields in EDITABLE_FIELDS
    for col in COLUMN_DEFS:
        if col["field"] in EDITABLE_FIELDS:
            col["editable"] = True
            col["cellStyle"] = {
                "styleConditions": [
                    {
                        "condition": "params.value === null || params.value === undefined || params.value === ''",
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
    submit_button = dmc.Button(
        "Run Range Optimization",
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

    # Category dropdown for Range Optimizer
    segment_dropdown = dmc.Select(
        id="category-select",  # Keep same ID for callback compatibility
        label="Select Product Category",
        data=[
            "All",
            "Beer & Seltzer",
            "Hot Sauce",
            "Ice Cream",
        ],
        searchable=True,
        value=None,
        w=400,
        persistence=True,
        persistence_type="local",
    )
    
    # Store cluster selector for range constraints
    store_selector = dmc.Select(
        id="store-cluster-select",
        label="Store Cluster",
        data=[
            {"value": "inner_city", "label": "Inner City Hipster (4.8m shelf)"},
            {"value": "suburban", "label": "Suburban BBQ (5.2m shelf)"},
            {"value": "regional", "label": "Regional Pub (3.6m shelf)"},
        ],
        value="inner_city",
        w=300,
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
        columnSize="sizeToFit",  # fit columns to viewport so headers stay visible
        className="ag-theme-quartz",
        dashGridOptions={
            "undoRedoCellEditing": True,
            "undoRedoCellEditingLimit": 20,
            "rowDragManaged": True,
            "rowDragEntireRow": True,
            "rowSelection": "multiple",
            "domLayout": "normal",
        },
        defaultColDef={
            "editable": False,
            "cellDataType": False,
            "sortable": True,
            "filter": True,
            "floatingFilter": True,
            "resizable": True,
            "minWidth": 100,
            "wrapHeaderText": True,   # wrap long header text
            "autoHeaderHeight": True, # let headers grow to show full name
        },
        csvExportParams={
            "fileName": "range_optimizer_skus.csv",
            "columnKeys": [col["field"] for col in COLUMN_DEFS],
            "skipColumnGroupHeaders": True,
        },
        rowClassRules={"ag-row-hover": "true"},
        style={
            "--ag-row-hover-color": "#f5f5f5",
            "height": "70vh",  # give the grid room so headers and rows are visible
        },
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
                        "Optimizing Range with HiGHS Solver", size="xl", fw=700, c="black"
                    ),
                ]
            ),
        },
        overlayProps={"radius": "sm", "blur": 2},
        visible=False,
    )

    # Store for the submitted optimization run ID
    forecast_id_store = dcc.Store(id="submitted-forecast-id", storage_type="session")
    
    # Constraints info card
    constraints_card = dmc.Paper(
        [
            dmc.Text("Range Constraints", fw=700, size="sm", mb=10),
            dmc.SimpleGrid(
                cols=4,
                spacing="md",
                children=[
                    dmc.Stack([
                        dmc.Text("Min SKUs", size="xs", c="dimmed"),
                        dmc.Text("10", fw=600),
                    ], gap=2),
                    dmc.Stack([
                        dmc.Text("Max SKUs", size="xs", c="dimmed"),
                        dmc.Text("15", fw=600),
                    ], gap=2),
                    dmc.Stack([
                        dmc.Text("Min PL Share", size="xs", c="dimmed"),
                        dmc.Text("0%", fw=600),
                    ], gap=2),
                    dmc.Stack([
                        dmc.Text("Max Brand Share", size="xs", c="dimmed"),
                        dmc.Text("30%", fw=600),
                    ], gap=2),
                ],
            ),
        ],
        p="md",
        radius="md",
        withBorder=True,
        style={"backgroundColor": "#fafafa"},
        id="constraints-card",
    )
    
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
                                    dmc.Text("Running Range Optimization", fw=700, size="lg"),
                                    dmc.Text(
                                        id="submission-status-text",
                                        children="Solving MIP with HiGHS...",
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
                                children="Preparing SKU demand data...",
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
                title="✅ Range Optimization Complete!",
                color="green",
                radius="md",
                children=[
                    dmc.Text(id="submission-forecast-id-text", size="sm"),
                    dmc.Space(h=10),
                    dmc.Group([
                        dcc.Link(
                            dmc.Button(
                                "View Planogram Results",
                                id="view-results-button",
                                color="red",
                                variant="filled",
                                leftSection=html.Span("📊"),
                                size="md",
                            ),
                            id="view-results-link",
                            href="/stock-optimization",
                            style={"textDecoration": "none"},
                        ),
                        dmc.Text("See recommended SKU assortment and facings allocation", size="xs", c="dimmed"),
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
            dmc.Group([segment_dropdown, store_selector], gap="xl"),
            dmc.Space(h=15),
            constraints_card,
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
                    submit_button,
                    overwrite_switch,
                ]
            ),
            # Submission progress (shown during processing)
            submission_progress,
            # Navigation to results appears after submission
            results_nav_card,
        ]
    )
