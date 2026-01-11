"""Stock Optimization Components"""

from typing import List, Dict, Any
import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import html, dcc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .ai_assistant import render_ai_assistant, render_key_insights, render_ai_chat_button, render_ai_chat_drawer


DEFAULT_COLUMN_DEFS: List[Dict[str, Any]] = [
    {"field": "SELL_ID", "headerName": "Sell ID", "filter": "agTextColumnFilter", "pinned": "left", "width": 110},
    {"field": "PRODUCT_NAME", "headerName": "Product", "filter": "agTextColumnFilter", "width": 200},
    {"field": "AVG_DAILY_DEMAND", "headerName": "Avg Daily Demand", "filter": "agNumberColumnFilter", "width": 150},
    {"field": "OPTIMAL_ORDER_QTY", "headerName": "Optimal Order Qty", "filter": "agNumberColumnFilter", "width": 160},
    {"field": "SAFETY_STOCK", "headerName": "Safety Stock", "filter": "agNumberColumnFilter", "width": 130},
    {"field": "REORDER_POINT", "headerName": "Reorder Point", "filter": "agNumberColumnFilter", "width": 140},
    {"field": "MAX_STOCK_LEVEL", "headerName": "Max Stock Level", "filter": "agNumberColumnFilter", "width": 150},
    {"field": "TOTAL_ANNUAL_COST", "headerName": "Annual Cost ($)", "filter": "agNumberColumnFilter", "width": 150,
     "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}},
    {"field": "EXPECTED_ANNUAL_REVENUE", "headerName": "Annual Revenue ($)", "filter": "agNumberColumnFilter", "width": 170,
     "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}},
    {"field": "EXPECTED_ANNUAL_PROFIT", "headerName": "Annual Profit ($)", "filter": "agNumberColumnFilter", "width": 160,
     "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}},
    {"field": "TURNOVER_RATE", "headerName": "Turnover Rate", "filter": "agNumberColumnFilter", "width": 140},
    {"field": "SERVICE_LEVEL", "headerName": "Service Level", "filter": "agNumberColumnFilter", "width": 130,
     "valueFormatter": {"function": "d3.format('.0%')(params.value)"}},
]


def create_summary_cards(summary_data: Dict[str, Any]) -> html.Div:
    """Create summary statistics cards"""
    if not summary_data:
        return html.Div()

    cards = [
        dmc.Card(
            children=[
                dmc.Text("Total Products", size="sm", c="dimmed"),
                dmc.Text(str(summary_data.get('total_products', 0)), size="xl", fw=700),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Total Optimal Stock", size="sm", c="dimmed"),
                dmc.Text(f"{summary_data.get('total_optimal_stock_units', 0):,.0f} units", size="xl", fw=700),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Total Annual Cost", size="sm", c="dimmed"),
                dmc.Text(f"${summary_data.get('total_annual_cost', 0):,.2f}", size="xl", fw=700, c="#E21837"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Total Annual Revenue", size="sm", c="dimmed"),
                dmc.Text(f"${summary_data.get('total_annual_revenue', 0):,.2f}", size="xl", fw=700, c="#00824B"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Total Annual Profit", size="sm", c="dimmed"),
                dmc.Text(f"${summary_data.get('total_annual_profit', 0):,.2f}", size="xl", fw=700, c="#E21837"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Avg Turnover Rate", size="sm", c="dimmed"),
                dmc.Text(f"{summary_data.get('avg_turnover_rate', 0):.2f}x", size="xl", fw=700),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
    ]

    return dmc.SimpleGrid(
        cols={"base": 1, "sm": 2, "lg": 3, "xl": 6},
        spacing="md",
        children=cards,
    )


def create_optimization_charts(optimization_df) -> html.Div:
    """Create visualization charts for optimization results"""
    if optimization_df is None or len(optimization_df) == 0:
        return html.Div()

    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Stock Levels by Product',
            'Cost vs Revenue by Product',
            'Turnover Rate Distribution',
            'Profit by Product'
        ),
        specs=[
            [{"type": "bar"}, {"type": "bar"}],
            [{"type": "histogram"}, {"type": "bar"}]
        ]
    )

    # Chart 1: Stock Levels by Product
    fig.add_trace(
        go.Bar(
            x=optimization_df['PRODUCT_NAME'],
            y=optimization_df['OPTIMAL_ORDER_QTY'],
            name='Optimal Order Qty',
            marker_color='lightblue'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Bar(
            x=optimization_df['PRODUCT_NAME'],
            y=optimization_df['SAFETY_STOCK'],
            name='Safety Stock',
            marker_color='orange'
        ),
        row=1, col=1
    )

    # Chart 2: Cost vs Revenue
    fig.add_trace(
        go.Bar(
            x=optimization_df['PRODUCT_NAME'],
            y=optimization_df['TOTAL_ANNUAL_COST'],
            name='Annual Cost',
            marker_color='red'
        ),
        row=1, col=2
    )
    fig.add_trace(
        go.Bar(
            x=optimization_df['PRODUCT_NAME'],
            y=optimization_df['EXPECTED_ANNUAL_REVENUE'],
            name='Annual Revenue',
            marker_color='green'
        ),
        row=1, col=2
    )

    # Chart 3: Turnover Rate Distribution
    fig.add_trace(
        go.Histogram(
            x=optimization_df['TURNOVER_RATE'],
            name='Turnover Rate',
            marker_color='purple',
            nbinsx=20
        ),
        row=2, col=1
    )

    # Chart 4: Profit by Product
    fig.add_trace(
        go.Bar(
            x=optimization_df['PRODUCT_NAME'],
            y=optimization_df['EXPECTED_ANNUAL_PROFIT'],
            name='Annual Profit',
            marker_color='blue'
        ),
        row=2, col=2
    )

    # Update layout
    fig.update_xaxes(tickangle=-45, row=1, col=1)
    fig.update_xaxes(tickangle=-45, row=1, col=2)
    fig.update_xaxes(title_text="Turnover Rate", row=2, col=1)
    fig.update_xaxes(tickangle=-45, row=2, col=2)

    fig.update_yaxes(title_text="Units", row=1, col=1)
    fig.update_yaxes(title_text="Amount ($)", row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=2, col=1)
    fig.update_yaxes(title_text="Profit ($)", row=2, col=2)

    fig.update_layout(
        height=800,
        showlegend=True,
        title_text="Stock Optimization Analysis",
        title_x=0.5,
    )

    return dcc.Graph(figure=fig, id='optimization-charts')


def fetch_forecast_ids_with_optimization() -> List[str]:
    """Fetch distinct forecast IDs that have optimization results."""
    try:
        from ..ml.forecast_optimizer import get_all_forecast_ids_with_optimization
        return get_all_forecast_ids_with_optimization()
    except Exception:
        return []


def render_stock_optimization_page() -> html.Div:
    """Render the stock optimization page layout"""

    # Forecast selector
    forecast_select = dmc.Select(
        id="optimization-forecast-select",
        label="Select Forecast Run to View Optimization",
        data=[{"value": fid, "label": fid} for fid in fetch_forecast_ids_with_optimization()],
        searchable=True,
        clearable=True,
        persistence=True,
        persistence_type="local",
        w=500,
    )

    # Download button
    download_button = dmc.Button(
        "Download Results CSV",
        id="optimization-csv-button",
        variant="filled",
        color="red",
        leftSection=html.I(className="fas fa-download"),
    )

    # AG-Grid for results
    grid = dag.AgGrid(
        id="optimization-results-grid",
        rowData=[],
        columnDefs=DEFAULT_COLUMN_DEFS,
        columnSize="autoSize",
        className="ag-theme-quartz",
        dashGridOptions={
            "rowSelection": "multiple",
            "suppressRowClickSelection": True,
            "pagination": True,
            "paginationPageSize": 20,
        },
        defaultColDef={
            "editable": False,
            "sortable": True,
            "filter": True,
            "floatingFilter": True,
            "resizable": True,
            "minWidth": 100,
        },
        csvExportParams={
            "fileName": "stock_optimization_results.csv",
            "skipColumnGroupHeaders": True,
        },
        style={"height": "500px"},
    )

    # Stores for data
    optimization_store = dcc.Store(id="optimization-data-store")
    summary_store = dcc.Store(id="optimization-summary-store")

    # Loading overlay
    loading = dcc.Loading(
        id="optimization-loading",
        type="default",
        children=html.Div(id="optimization-loading-output")
    )

    # Alert/notification
    alert = dmc.Alert(
        id="optimization-alert",
        title="Stock Optimization Results",
        color="blue",
        children="Select a forecast run above to view its stock optimization results.",
        radius="md",
    )

    # Hidden trigger for page load
    page_load_trigger = html.Div(id="optimization-page-load", style={"display": "none"})

    # AI Assistant components
    ai_assistant = render_ai_assistant()

    return html.Div([
        page_load_trigger,
        optimization_store,
        summary_store,
        # AI Assistant stores and drawer (rendered by ai_assistant)
        ai_assistant,
        dmc.Space(h=20),
        dmc.Title("Stock Optimization", order=2, c="#E21837"),
        dmc.Space(h=10),
        dmc.Text(
            "View stock optimization results for your forecast runs. Our EOQ-based model calculates optimal order quantities, safety stock levels, and reorder points to maximize profitability across all product categories.",
            size="md",
            c="dimmed"
        ),
        dmc.Space(h=20),
        forecast_select,
        dmc.Space(h=10),
        alert,
        dmc.Space(h=20),
        # Key Insights - shows after forecast selected (rendered inside ai_assistant)
        dmc.Space(h=10),
        dmc.Group([download_button], gap="md"),
        dmc.Space(h=20),
        loading,
        html.Div(id="optimization-summary-cards"),
        dmc.Space(h=20),
        html.Div(id="optimization-charts-container"),
        dmc.Space(h=20),
        dmc.Text("Detailed Results:", size="lg", fw=600),
        dmc.Space(h=10),
        grid,
        dmc.Space(h=80),  # Extra space for floating button
    ])
