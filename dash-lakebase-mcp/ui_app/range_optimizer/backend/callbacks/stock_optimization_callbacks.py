"""
Callbacks for Range Optimization Results page.

Handles:
- Populating the optimization run dropdown
- Loading and displaying optimization results
- Summary cards and charts

All data operations go through the MCP client - no direct database access!
"""

import datetime
from typing import Dict, Any, List, Tuple
from urllib.parse import parse_qs, unquote

import pandas as pd
import dash_mantine_components as dmc
from dash import Input, Output, callback, html

# Use MCP client for all data operations
from ..mcp_client import get_optimization_runs, get_optimization_results

from ..components.stock_optimization import create_summary_cards, create_optimization_charts


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


# =============================================================================
# 1. Populate Run Dropdown (via MCP)
# =============================================================================

@callback(
    Output("optimization-forecast-select", "data"),
    Output("optimization-forecast-select", "value"),
    Input("optimization-page-load", "id"),
    Input("url", "search"),
    prevent_initial_call=False,
)
def populate_run_dropdown(_: str, search: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Populate the optimization run dropdown with available runs from MCP.
    Auto-selects run if passed via URL query parameter.
    """
    log(f"CALLBACK: populate_run_dropdown - search: {search}")
    
    # Parse query parameters
    run_from_url = None
    if search:
        try:
            decoded_search = unquote(search.lstrip("?"))
            log(f"→ Decoded search: {decoded_search}")
            params = parse_qs(decoded_search)
            run_from_url = params.get("forecast", [None])[0]
            log(f"→ Run ID from URL: {run_from_url}")
        except Exception as e:
            log(f"Error parsing URL params: {e}")
    
    # Fetch runs from MCP server
    response = get_optimization_runs(limit=50)
    
    if response.success and response.data:
        runs = response.data
        run_ids = [r.get("run_id") for r in runs if r.get("run_id")]
        log(f"✓ Found {len(run_ids)} optimization runs from MCP")
        
        dropdown_data = [{"value": rid, "label": rid} for rid in run_ids]
        
        # Auto-select run from URL if it exists
        selected_value = None
        if run_from_url and run_from_url in run_ids:
            selected_value = run_from_url
            log(f"✓ Auto-selecting run from URL: {selected_value}")
        
        return dropdown_data, selected_value
    else:
        log(f"⚠️ Error fetching runs: {response.error}")
        return [], None


# =============================================================================
# 2. Load Optimization Results (via MCP)
# =============================================================================

@callback(
    Output("optimization-data-store", "data"),
    Output("optimization-summary-store", "data"),
    Output("optimization-alert", "children"),
    Output("optimization-alert", "color"),
    Input("optimization-forecast-select", "value"),
    prevent_initial_call=True,
)
def load_optimization_results(run_id: str) -> Tuple[List[Dict], Dict, str, str]:
    """
    Load range optimization results for the selected run from MCP.
    """
    log(f"CALLBACK: load_optimization_results - run_id: {run_id}")

    if not run_id:
        return [], {}, "Select an optimization run to view planogram recommendations.", "blue"

    try:
        log(f"→ Loading results from MCP for run: {run_id}")
        
        # Fetch from MCP server
        response = get_optimization_results(run_id)
        
        if not response.success:
            log(f"⚠️ MCP error: {response.error}")
            return [], {}, f"Error loading results: {response.error}", "red"
        
        results = response.data.get("results", [])
        summary = response.data.get("summary", {})
        
        if not results:
            log(f"⚠️ No results found for run: {run_id}")
            return [], {}, f"No results found for run {run_id}", "yellow"
        
        log(f"✓ Loaded {len(results)} results from MCP")
        
        # Convert to DataFrame for processing
        df = pd.DataFrame(results)
        
        # Uppercase columns for UI consistency
        df.columns = [col.upper() for col in df.columns]
        optimization_results = df.to_dict('records')
        
        # Build summary for UI (supplement from API if needed)
        ui_summary = build_ui_summary(df, summary, run_id)
        log("✓ Summary built")

        # Build alert message
        ranged_skus = summary.get("skus_in_range", len(df))
        total_skus = summary.get("total_skus", len(df))
        total_profit = summary.get("total_weekly_profit", 0)
        
        alert_message = dmc.Text([
            html.B(f"Range Optimization Results: {run_id}"),
            html.Br(),
            f"Optimized {ranged_skus} SKUs in range (of {total_skus} evaluated). ",
            f"Expected weekly profit: ${total_profit:,.2f}",
        ])

        log("✅ Range optimization results loaded successfully")
        return optimization_results, ui_summary, alert_message, "green"

    except Exception as e:
        log(f"❌ Error loading optimization results: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], {}, f"Error loading results: {str(e)}", "red"


def build_ui_summary(df: pd.DataFrame, api_summary: Dict, run_id: str) -> Dict[str, Any]:
    """Build summary dict for UI components from MCP response."""
    
    # Use API summary values where available, calculate from df as fallback
    ranged_count = api_summary.get("skus_in_range", len(df))
    
    # Get change counts from API or calculate
    skus_added = api_summary.get("skus_added", 0)
    skus_removed = api_summary.get("skus_removed", 0)
    skus_increased = api_summary.get("skus_increased", 0)
    skus_decreased = api_summary.get("skus_decreased", 0)
    
    # Calculate totals
    total_facings = api_summary.get("total_facings", 0)
    if not total_facings and "RECOMMENDED_FACINGS" in df.columns:
        total_facings = int(df["RECOMMENDED_FACINGS"].sum())
    
    total_weekly_profit = api_summary.get("total_weekly_profit", 0)
    if not total_weekly_profit and "EXPECTED_MARGIN_WEEKLY" in df.columns:
        total_weekly_profit = df["EXPECTED_MARGIN_WEEKLY"].sum()
    
    # Private label share (calculate from df if we have brand data)
    pl_brands = ['Coles', 'Woolworths', 'Generic', 'Home Brand']
    pl_share = 0
    if "BRAND" in df.columns and total_facings > 0:
        pl_facings = df[df["BRAND"].isin(pl_brands)]["RECOMMENDED_FACINGS"].sum() if "RECOMMENDED_FACINGS" in df.columns else 0
        pl_share = (pl_facings / total_facings * 100)
    
    # Space utilization estimate
    shelf_width_mm = 3600
    pack_width_mm = 170
    space_used_mm = total_facings * pack_width_mm
    space_utilization = min((space_used_mm / shelf_width_mm * 100), 100) if shelf_width_mm > 0 else 0
    
    return {
        'run_id': run_id,
        'total_skus_evaluated': api_summary.get("total_skus", len(df)),
        'skus_in_range': ranged_count,
        'skus_added': skus_added,
        'skus_removed': skus_removed,
        'skus_facings_increased': skus_increased,
        'skus_facings_decreased': skus_decreased,
        'total_weekly_profit': total_weekly_profit,
        'total_facings': int(total_facings),
        'private_label_share_pct': pl_share,
        'space_utilization_pct': space_utilization,
    }


# =============================================================================
# 3. Update Grid
# =============================================================================

@callback(
    Output("optimization-results-grid", "rowData"),
    Input("optimization-data-store", "data"),
)
def update_optimization_grid(optimization_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update the AG-Grid with optimization results."""
    log(f"CALLBACK: update_optimization_grid - rows: {len(optimization_data) if optimization_data else 0}")
    return optimization_data or []


# =============================================================================
# 4. Update Summary Cards
# =============================================================================

@callback(
    Output("optimization-summary-cards", "children"),
    Input("optimization-summary-store", "data"),
)
def update_summary_cards(summary_data: Dict[str, Any]):
    """Update the summary statistics cards."""
    log(f"CALLBACK: update_summary_cards - has_data: {bool(summary_data)}")
    if not summary_data:
        return html.Div()
    return create_summary_cards(summary_data)


# =============================================================================
# 5. Update Charts
# =============================================================================

@callback(
    Output("optimization-charts-container", "children"),
    Input("optimization-data-store", "data"),
)
def update_optimization_charts(optimization_data: List[Dict[str, Any]]):
    """Update the optimization visualization charts."""
    log(f"CALLBACK: update_optimization_charts - rows: {len(optimization_data) if optimization_data else 0}")

    if not optimization_data:
        return html.Div()

    df = pd.DataFrame(optimization_data)
    return create_optimization_charts(df)


# =============================================================================
# 6. Export CSV
# =============================================================================

@callback(
    Output("optimization-results-grid", "exportDataAsCsv"),
    Input("optimization-csv-button", "n_clicks"),
)
def export_optimization_csv(n_clicks: int) -> bool:
    """Export optimization results to CSV."""
    log(f"CALLBACK: export_optimization_csv - n_clicks: {n_clicks}")
    if n_clicks:
        return True
    return False
