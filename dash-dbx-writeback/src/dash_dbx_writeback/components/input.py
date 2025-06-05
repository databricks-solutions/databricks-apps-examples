from typing import List, Dict, Any, Optional

import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import html, dcc, no_update, callback, clientside_callback, register_page

from .tabs import tabs
from ..data.sample_product_data import INITIAL_DATA

EDITABLE_FIELDS = [
    "SELL_ID",
    "LOYALTY_GROUP",
    "SEGMENT_1",
    "SEGMENT_2",
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
    {
        "field": "CURRENT_ASSORTMENT",
        "headerName": "Current Assortment",
        "filter": "agTextColumnFilter",
    },
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
}


def get_null_description(data: Optional[List[Dict[str, Any]]] = None) -> dmc.Stack:
    issues: List[str] = []
    duplicate_sell_ids: List[str] = []
    if data:
        sell_id_counts: Dict[str, int] = {}
        for row in data:
            sell_id = row.get("SELL_ID")
            if sell_id:
                sell_id_counts[sell_id] = sell_id_counts.get(sell_id, 0) + 1
        duplicate_sell_ids = [sid for sid, count in sell_id_counts.items() if count > 1]

        for i, row in enumerate(data):
            missing = [field for field in EDITABLE_FIELDS if not row.get(field)]
            if missing:
                issues.append(
                    f"Row {i+1} (ID: {row.get('SELL_ID', 'N/A')}): missing {', '.join(missing)}"
                )

    alerts: List[dmc.Alert] = []
    if duplicate_sell_ids:
        alerts.append(
            dmc.Alert(
                title="Duplicate SELL_IDs found",
                color="yellow",
                radius="md",
                children=[
                    "The following SELL_IDs are duplicated:",
                    dmc.List(
                        [dmc.ListItem(sid) for sid in duplicate_sell_ids],
                        size="sm",
                        mt=5,
                    ),
                ],
                style={"marginBottom": "8px"},
            )
        )
    if issues:
        alerts.append(
            dmc.Alert(
                title="Some required fields are missing",
                color="red",
                radius="md",
                children=[
                    dmc.List([dmc.ListItem(issue) for issue in issues], size="sm")
                ],
                style={"marginBottom": "8px"},
            )
        )
    if not alerts and data:
        alerts.append(
            dmc.Alert(
                title="All required fields are filled",
                color="green",
                radius="md",
                children="You can proceed with submitting the data.",
                style={"marginBottom": "8px"},
            )
        )
    if not data:
        alerts.append(
            dmc.Alert(
                title="Begin by picking your product category above",
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
        variant="gradient",
        id="reset-button",
        n_clicks=0,
        gradient={"from": "orange", "to": "red"},
    )
    download_button = dmc.Button(
        "Download CSV", variant="gradient", id="csv-button", n_clicks=0
    )
    sumbit_button = dmc.Button(
        "Submit Forecast Run", variant="gradient", id="submit-button", n_clicks=0
    )
    delete_button = dmc.Button(
        "Delete Rows", variant="gradient", id="delete-button", n_clicks=0,
        gradient={"from": "red", "to": "orange"},
    )
    upload_button = dcc.Upload(
        id="upload-data",
        children=dmc.Button("Upload CSV", variant="gradient"),
        multiple=False,
    )

    # Add a Store component to maintain the data state
    store = dcc.Store(id="grid-data-store", storage_type="local")

    # Add category dropdown to main layout
    category_dropdown = dmc.Select(
        id="category-select",
        label="Pick your category",
        data=["All", "Dairy", "Bakery", "Confectionery"],
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
            'undoRedoCellEditing': True,
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

    info_box = html.Div(
        get_null_description(data=None), id="info-box"
    )

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

    return html.Div(
        [
            html.Div(
                id="page-load", style={"display": "none"}
            ),  # Hidden div for initialization trigger
            store,
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
        ]
    )
