from dash import dash_table
from dash_iconify import DashIconify


def get_icon(icon):
    return DashIconify(icon=icon, height=16)


def create_data_table(id):
    return dash_table.DataTable(
        id=id,
        style_table={"marginTop": "20px", "width": "100%", "overflowX": "auto"},
        style_header={
            "backgroundColor": "#EEEDE9",
            "fontWeight": "bold",
            "fontFamily": "DM Sans, sans-serif",
            "border": "1px solid #DCDCDC",
        },
        style_cell={
            "textAlign": "left",
            "padding": "10px",
            "fontFamily": "DM Sans, sans-serif",
            "minWidth": "100px",
            "width": "150px",
            "maxWidth": "300px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "border": "1px solid #DCDCDC",
        },
        style_data={
            "whiteSpace": "normal",
            "height": "auto",
            "backgroundColor": "#FFFFFF",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#F9F7F4",
            }
        ],
        page_size=10,
        sort_action="native",
        filter_action="native",
        tooltip_delay=0,
        tooltip_duration=None,
        tooltip_data=[
            {
                column: {"value": str(value), "type": "markdown"}
                for column, value in row.items()
            }
            for row in [{}]
        ],
        virtualization=True,
        fixed_rows={"headers": True},
    )
