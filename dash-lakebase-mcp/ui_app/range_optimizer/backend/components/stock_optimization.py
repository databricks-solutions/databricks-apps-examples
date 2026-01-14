"""Range Optimization Components - Planogram Results Display"""

from typing import List, Dict, Any
import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import html, dcc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .ai_assistant import render_key_insights, render_ai_chat_button, render_ai_chat_drawer


# Column definitions for Range Optimization results grid
# Column names match the opt_recommended_planogram schema (uppercase after API conversion)
DEFAULT_COLUMN_DEFS: List[Dict[str, Any]] = [
    {"field": "SKU_ID", "headerName": "SKU ID", "filter": "agTextColumnFilter", "pinned": "left", "width": 120},
    {"field": "SKU_NAME", "headerName": "Product", "filter": "agTextColumnFilter", "width": 200},
    {"field": "CATEGORY", "headerName": "Category", "filter": "agTextColumnFilter", "width": 130},
    {"field": "BRAND", "headerName": "Brand", "filter": "agTextColumnFilter", "width": 120},
    {"field": "CURRENT_FACINGS", "headerName": "Current", "filter": "agNumberColumnFilter", "width": 100},
    {"field": "RECOMMENDED_FACINGS", "headerName": "Recommended", "filter": "agNumberColumnFilter", "width": 130,
     "cellStyle": {"fontWeight": "bold"}},
    {
        "field": "FACINGS_CHANGE", 
        "headerName": "Change", 
        "filter": "agNumberColumnFilter", 
        "width": 100,
        "cellStyle": {
            "styleConditions": [
                {"condition": "params.value > 0", "style": {"color": "#00824B", "fontWeight": "bold"}},
                {"condition": "params.value < 0", "style": {"color": "#E21837", "fontWeight": "bold"}},
                {"condition": "params.value === 0", "style": {"color": "#666"}},
            ]
        },
        "valueFormatter": {"function": "params.value > 0 ? '+' + params.value : params.value"},
    },
    {
        "field": "CHANGE_FROM_CURRENT",  # New schema column name
        "headerName": "Action",
        "filter": "agTextColumnFilter",
        "width": 110,
        "cellStyle": {
            "styleConditions": [
                {"condition": "params.value === 'new'", "style": {"backgroundColor": "#d4edda", "color": "#155724"}},
                {"condition": "params.value === 'removed'", "style": {"backgroundColor": "#f8d7da", "color": "#721c24"}},
                {"condition": "params.value === 'increased'", "style": {"backgroundColor": "#d1ecf1", "color": "#0c5460"}},
                {"condition": "params.value === 'decreased'", "style": {"backgroundColor": "#fff3cd", "color": "#856404"}},
            ]
        },
    },
    {"field": "EXPECTED_UNITS_WEEKLY", "headerName": "Weekly Units", "filter": "agNumberColumnFilter", "width": 120},
    {"field": "EXPECTED_MARGIN_WEEKLY", "headerName": "Weekly Profit ($)", "filter": "agNumberColumnFilter", "width": 140,
     "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}},
    {"field": "EXPECTED_SALES_VALUE_WEEKLY", "headerName": "Weekly Sales ($)", "filter": "agNumberColumnFilter", "width": 140,
     "valueFormatter": {"function": "d3.format(',.2f')(params.value)"}},
    {"field": "IS_MUST_STOCK", "headerName": "Must Stock", "filter": "agTextColumnFilter", "width": 100,
     "cellRenderer": "agCheckboxCellRenderer"},
    {"field": "IS_RANGED_RECOMMENDED", "headerName": "In Range", "filter": "agTextColumnFilter", "width": 100,
     "cellRenderer": "agCheckboxCellRenderer"},
]


def create_summary_cards(summary_data: Dict[str, Any]) -> html.Div:
    """Create summary statistics cards for range optimization"""
    if not summary_data:
        return html.Div()

    cards = [
        dmc.Card(
            children=[
                dmc.Text("SKUs in Range", size="sm", c="dimmed"),
                dmc.Text(str(summary_data.get('skus_in_range', 0)), size="xl", fw=700),
                dmc.Text(f"of {summary_data.get('total_skus_evaluated', 0)} evaluated", size="xs", c="dimmed"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Group([
                    dmc.Stack([
                        dmc.Text("Added", size="xs", c="dimmed"),
                        dmc.Text(f"+{summary_data.get('skus_added', 0)}", size="lg", fw=700, c="#00824B"),
                    ], gap=2),
                    dmc.Stack([
                        dmc.Text("Removed", size="xs", c="dimmed"),
                        dmc.Text(f"-{summary_data.get('skus_removed', 0)}", size="lg", fw=700, c="#E21837"),
                    ], gap=2),
                ], gap="xl"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Total Facings", size="sm", c="dimmed"),
                dmc.Text(str(summary_data.get('total_facings', 0)), size="xl", fw=700),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Weekly Profit", size="sm", c="dimmed"),
                dmc.Text(f"${summary_data.get('total_weekly_profit', 0):,.2f}", size="xl", fw=700, c="#00824B"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Private Label Share", size="sm", c="dimmed"),
                dmc.Text(f"{summary_data.get('private_label_share_pct', 0):.1f}%", size="xl", fw=700),
                dmc.Text("Target: ≥20%", size="xs", c="dimmed"),
            ],
            withBorder=True,
            padding="md",
            radius="md",
        ),
        dmc.Card(
            children=[
                dmc.Text("Space Utilization", size="sm", c="dimmed"),
                dmc.Text(f"{summary_data.get('space_utilization_pct', 0):.1f}%", size="xl", fw=700),
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
    """Create beautiful visualization charts for range optimization results.
    
    Handles various column name formats from the API (uppercase after conversion).
    Features enhanced styling with dark theme, modern colors, and rich interactivity.
    """
    if optimization_df is None or len(optimization_df) == 0:
        return html.Div()

    df = optimization_df.copy()
    
    # Determine ranged column (handle various naming conventions)
    ranged_col = None
    for col in ['IS_RANGED_RECOMMENDED', 'IS_RANGED', 'RANGED']:
        if col in df.columns:
            ranged_col = col
            break
    
    if ranged_col:
        ranged_df = df[df[ranged_col] == True]
    else:
        ranged_df = df
    
    if len(ranged_df) == 0:
        ranged_df = df  # Fallback to all data
    
    # Helper to get column with fallback
    def get_col(primary, *fallbacks):
        for col in [primary] + list(fallbacks):
            if col in ranged_df.columns:
                return col
        return None
    
    # Column mappings (new schema → old schema fallbacks)
    sku_col = get_col('SKU_NAME', 'SKU_ID', 'PRODUCT_NAME')
    brand_col = get_col('BRAND', 'CATEGORY')  # Use CATEGORY as fallback
    facings_col = get_col('RECOMMENDED_FACINGS', 'FACINGS', 'OPTIMAL_FACINGS')
    current_col = get_col('CURRENT_FACINGS', 'EXISTING_FACINGS')
    profit_col = get_col('EXPECTED_MARGIN_WEEKLY', 'SPACE_PRODUCTIVITY', 'WEEKLY_PROFIT')
    segment_col = get_col('SEGMENT', 'CATEGORY', 'BRAND')
    
    # ═══════════════════════════════════════════════════════════════
    # COLES GROUP THEME - Red accent, light background, high contrast
    # ═══════════════════════════════════════════════════════════════
    COLES_RED = '#E01A22'           # Coles primary red
    COLES_DARK_RED = '#B8151B'      # Darker red for contrast
    
    # Color palette with Coles red as hero, complementary colors
    PIE_COLORS_PRIMARY = [
        '#E01A22',  # Coles Red (hero)
        '#2D9CDB',  # Corporate Blue
        '#27AE60',  # Fresh Green
        '#F2994A',  # Warm Orange
        '#9B51E0',  # Purple accent
        '#56CCF2',  # Light Blue
        '#EB5757',  # Soft Red
        '#F2C94C',  # Yellow
    ]
    PIE_COLORS_SECONDARY = [
        '#2D9CDB',  # Corporate Blue
        '#27AE60',  # Fresh Green  
        '#E01A22',  # Coles Red
        '#F2994A',  # Warm Orange
        '#9B51E0',  # Purple accent
        '#56CCF2',  # Light Blue
    ]
    
    # Light theme colors for white page background
    PLOT_BG = '#FFFFFF'                      # White background
    PAPER_BG = '#FFFFFF'                     # White paper
    GRID_COLOR = 'rgba(0, 0, 0, 0.08)'       # Subtle gray grid
    TEXT_COLOR = '#1F2937'                   # Dark slate for text
    SUBTITLE_COLOR = '#374151'               # Slightly lighter for subtitles
    AXIS_COLOR = '#4B5563'                   # Gray for axis labels

    # Create subplots with better spacing
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f'🏷️ Facings by {brand_col or "Category"}',
            '📊 Current vs Recommended',
            '💰 Profit Potential by SKU',
            f'🎯 {segment_col or "Segment"} Distribution'
        ),
        specs=[
            [{"type": "pie"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "pie"}]
        ],
        horizontal_spacing=0.12,
        vertical_spacing=0.25,  # More space between top and bottom rows
    )

    # ═══════════════════════════════════════════════════════════════
    # CHART 1: Facings by Brand (Enhanced Donut) - Coles Theme
    # ═══════════════════════════════════════════════════════════════
    if brand_col and facings_col:
        brand_facings = ranged_df.groupby(brand_col)[facings_col].sum().reset_index()
        fig.add_trace(
            go.Pie(
                labels=brand_facings[brand_col],
                values=brand_facings[facings_col],
                name='Brand Share',
                hole=0.5,
                marker=dict(
                    colors=PIE_COLORS_PRIMARY[:len(brand_facings)],
                    line=dict(color='#FFFFFF', width=2)
                ),
                textinfo='percent+label',
                textposition='outside',
                textfont=dict(size=11, color=TEXT_COLOR, family="system-ui, -apple-system, sans-serif"),
                hovertemplate="<b>%{label}</b><br>" +
                              "Facings: %{value:,.0f}<br>" +
                              "Share: %{percent}<extra></extra>",
                pull=[0.015] * len(brand_facings),
            ),
            row=1, col=1
        )

    # ═══════════════════════════════════════════════════════════════
    # CHART 2: Current vs Recommended (Grouped Bar) - Coles Theme
    # ═══════════════════════════════════════════════════════════════
    if sku_col and facings_col:
        x_labels = ranged_df[sku_col].astype(str).str[:15]
        
        if current_col:
            fig.add_trace(
                go.Bar(
                    x=x_labels,
                    y=ranged_df[current_col],
                    name='Current',
                    marker=dict(
                        color='#9CA3AF',  # Gray for current
                        line=dict(width=0),
                    ),
                    hovertemplate="<b>%{x}</b><br>Current: %{y} facings<extra></extra>",
                ),
                row=1, col=2
            )
        
        fig.add_trace(
            go.Bar(
                x=x_labels,
                y=ranged_df[facings_col],
                name='Recommended',
                marker=dict(
                    color=COLES_RED,  # Coles red for recommended
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{x}</b><br>Recommended: %{y} facings<extra></extra>",
            ),
            row=1, col=2
        )

    # ═══════════════════════════════════════════════════════════════
    # CHART 3: Profit Potential (Horizontal Bar) - Coles Theme
    # ═══════════════════════════════════════════════════════════════
    if sku_col and profit_col:
        productivity_df = ranged_df.sort_values(profit_col, ascending=True).head(12)
        median_val = productivity_df[profit_col].median() if len(productivity_df) > 0 else 0
        
        # Coles-themed conditional colors
        colors = []
        for x in productivity_df[profit_col]:
            if x >= median_val * 1.2:
                colors.append('#E01A22')  # Coles red - top performers
            elif x >= median_val:
                colors.append('#27AE60')  # Green - above average
            else:
                colors.append('#9CA3AF')  # Gray - below average
        
        fig.add_trace(
            go.Bar(
                x=productivity_df[profit_col],
                y=productivity_df[sku_col].astype(str).str[:18],
                orientation='h',
                name='Weekly Profit',
                marker=dict(
                    color=colors,
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>Weekly Profit: $%{x:,.2f}<extra></extra>",
            ),
            row=2, col=1
        )

    # ═══════════════════════════════════════════════════════════════
    # CHART 4: Segment Distribution (Enhanced Donut) - Coles Theme
    # ═══════════════════════════════════════════════════════════════
    if segment_col and facings_col:
        segment_facings = ranged_df.groupby(segment_col)[facings_col].sum().reset_index()
        fig.add_trace(
            go.Pie(
                labels=segment_facings[segment_col],
                values=segment_facings[facings_col],
                name='Segment Share',
                hole=0.5,
                marker=dict(
                    colors=PIE_COLORS_SECONDARY[:len(segment_facings)],
                    line=dict(color='#FFFFFF', width=2)
                ),
                textinfo='percent+label',
                textposition='outside',
                textfont=dict(size=11, color=TEXT_COLOR, family="system-ui, -apple-system, sans-serif"),
                hovertemplate="<b>%{label}</b><br>" +
                              "Facings: %{value:,.0f}<br>" +
                              "Share: %{percent}<extra></extra>",
            ),
            row=2, col=2
        )

    # ═══════════════════════════════════════════════════════════════
    # GLOBAL LAYOUT - Coles Light Theme
    # ═══════════════════════════════════════════════════════════════
    fig.update_layout(
        height=900,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
            bgcolor='rgba(255,255,255,0.95)',
            font=dict(color=TEXT_COLOR, size=10),
            bordercolor='#E5E7EB',
            borderwidth=1,
            tracegroupgap=5,
        ),
        title=dict(
            text="<b>Range Optimization Analysis</b>",
            x=0.5,
            y=0.98,
            font=dict(size=22, color=COLES_RED, family="system-ui, -apple-system, sans-serif"),
        ),
        barmode='group',
        bargap=0.2,
        bargroupgap=0.1,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="system-ui, -apple-system, sans-serif", color=TEXT_COLOR),
        margin=dict(t=80, b=120, l=60, r=40),
    )
    
    # Style subplot titles - dark text for light background, pushed up slightly
    for annotation in fig.layout.annotations:
        annotation.font = dict(size=14, color=TEXT_COLOR, family="system-ui, -apple-system, sans-serif")
        annotation.y = annotation.y + 0.03  # Push titles up to avoid overlap with pie labels
    
    # Update axes styling for bar charts - Light theme
    fig.update_xaxes(
        tickangle=-45,
        tickfont=dict(size=10, color=AXIS_COLOR),
        gridcolor=GRID_COLOR,
        showline=True,
        linecolor='#E5E7EB',
        row=1, col=2
    )
    fig.update_xaxes(
        title_text="Weekly Profit ($)",
        title_font=dict(size=11, color=TEXT_COLOR),
        tickfont=dict(size=10, color=AXIS_COLOR),
        gridcolor=GRID_COLOR,
        tickprefix="$",
        row=2, col=1
    )
    
    fig.update_yaxes(
        title_text="Facings",
        title_font=dict(size=11, color=TEXT_COLOR),
        tickfont=dict(size=10, color=AXIS_COLOR),
        gridcolor=GRID_COLOR,
        row=1, col=2
    )
    fig.update_yaxes(
        tickfont=dict(size=10, color=AXIS_COLOR),
        gridcolor=GRID_COLOR,
        row=2, col=1
    )

    return dcc.Graph(
        figure=fig,
        id='optimization-charts',
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        },
        style={'borderRadius': '12px', 'overflow': 'hidden'}
    )


def fetch_forecast_ids_with_optimization() -> List[str]:
    """Fetch distinct optimization run IDs that have results via MCP."""
    try:
        from ..mcp_client import get_optimization_runs
        response = get_optimization_runs(limit=50)
        if response.success:
            return [r.get("run_id") for r in response.data if r.get("run_id")]
        return []
    except Exception:
        return []


def render_stock_optimization_page() -> html.Div:
    """Render the range optimization results page layout"""

    # Run selector - populated via callback to avoid startup race condition
    run_select = dmc.Select(
        id="optimization-forecast-select",
        label="Select Optimization Run",
        data=[],  # Populated by populate_run_dropdown callback
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
            "fileName": "range_optimization_results.csv",
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
        title="Range Optimization Results",
        color="blue",
        children="Select an optimization run above to view recommended planogram.",
        radius="md",
    )

    # Hidden trigger for page load
    page_load_trigger = html.Div(id="optimization-page-load", style={"display": "none"})
    
    # Legend for change types
    legend = dmc.Paper(
        [
            dmc.Text("Action Legend:", size="sm", fw=600, mb=5),
            dmc.Group([
                dmc.Badge("new", color="green", variant="light"),
                dmc.Text("Added to range", size="xs"),
                dmc.Badge("removed", color="red", variant="light"),
                dmc.Text("Dropped from range", size="xs"),
                dmc.Badge("increased", color="cyan", variant="light"),
                dmc.Text("More facings", size="xs"),
                dmc.Badge("decreased", color="yellow", variant="light"),
                dmc.Text("Fewer facings", size="xs"),
            ], gap="xs"),
        ],
        p="sm",
        radius="md",
        withBorder=True,
        style={"backgroundColor": "#fafafa"},
    )

    return html.Div([
        page_load_trigger,
        optimization_store,
        summary_store,
        # AI Assistant stores, button and drawer
        html.Div([
            dcc.Store(id="ai-forecast-context", storage_type="memory"),
            dcc.Store(id="ai-chat-history", storage_type="memory", data=[]),
            html.Div(id="ai-loading-output", style={"display": "none"}),
            render_ai_chat_button(),
            render_ai_chat_drawer(),
        ]),
        dmc.Space(h=20),
        dmc.Title("Range Optimization Results", order=2, c="#E21837"),
        dmc.Space(h=10),
        dmc.Text(
            "View recommended assortment and planogram from the HiGHS-based optimizer. "
            "The model maximizes category profit while respecting shelf space constraints, "
            "must-stock rules, and private label share targets.",
            size="md",
            c="dimmed"
        ),
        dmc.Space(h=20),
        run_select,
        dmc.Space(h=10),
        alert,
        dmc.Space(h=20),
        loading,
        html.Div(id="optimization-summary-cards"),
        dmc.Space(h=20),
        html.Div(id="optimization-charts-container"),
        dmc.Space(h=20),
        dmc.Group([download_button], gap="md"),
        dmc.Space(h=20),
        # Key Insights from AI
        render_key_insights(),
        dmc.Space(h=20),
        legend,
        dmc.Space(h=10),
        dmc.Text("Recommended Planogram:", size="lg", fw=600),
        dmc.Space(h=10),
        grid,
        dmc.Space(h=80),  # Extra space for floating button
    ])
