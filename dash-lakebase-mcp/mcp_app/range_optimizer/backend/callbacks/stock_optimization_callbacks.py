"""Callbacks for Range Optimization Results page"""

import datetime
from typing import Dict, Any, List, Tuple
from urllib.parse import parse_qs, urlparse, unquote
import pandas as pd
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, html

from ..components.stock_optimization import create_summary_cards, create_optimization_charts


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


@callback(
    Output("optimization-forecast-select", "data"),
    Output("optimization-forecast-select", "value"),
    Input("optimization-page-load", "id"),
    Input("url", "search"),
    prevent_initial_call=False,
)
def populate_run_dropdown(_: str, search: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Populate the optimization run dropdown with available runs.
    Also auto-select run if passed via URL query parameter.
    """
    log(f"CALLBACK: populate_run_dropdown - search: {search}")
    
    # Parse query parameters
    run_from_url = None
    if search:
        try:
            # Handle double-encoded URLs
            decoded_search = unquote(search.lstrip("?"))
            log(f"→ Decoded search: {decoded_search}")
            params = parse_qs(decoded_search)
            run_from_url = params.get("forecast", [None])[0]
            log(f"→ Run ID from URL: {run_from_url}")
        except Exception as e:
            log(f"Error parsing URL params: {e}")
    
    try:
        from ..ml.forecast_optimizer import get_all_forecast_ids_with_optimization
        run_ids = get_all_forecast_ids_with_optimization()
        log(f"✓ Found {len(run_ids)} optimization runs")
        
        dropdown_data = [{"value": rid, "label": rid} for rid in run_ids]
        
        # Auto-select run from URL if it exists in the list
        selected_value = None
        if run_from_url and run_from_url in run_ids:
            selected_value = run_from_url
            log(f"✓ Auto-selecting run from URL: {selected_value}")
        
        return dropdown_data, selected_value
    except Exception as e:
        log(f"⚠️ Error fetching run IDs: {e}")
        # Return demo data for demonstration
        demo_runs = [
            {"value": "OPT-20260110-demo", "label": "OPT-20260110-demo (Demo Run)"},
        ]
        selected = "OPT-20260110-demo" if run_from_url else None
        return demo_runs, selected


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
    Load range optimization results for the selected run.

    Returns:
        - Optimization results data
        - Summary statistics
        - Alert message
        - Alert color
    """
    log(f"CALLBACK: load_optimization_results - run_id: {run_id}")

    if not run_id:
        return [], {}, "Select an optimization run to view planogram recommendations.", "blue"

    try:
        log(f"→ Loading optimization results for run: {run_id}")
        
        # Try to load from database first
        try:
            from ..ml.forecast_optimizer import get_optimization_results
            optimized_df = get_optimization_results(run_id)
            
            if optimized_df.empty:
                raise ValueError("No results found")
                
            log(f"✓ Found {len(optimized_df)} optimization results from database")
            
        except Exception as db_error:
            log(f"⚠️ Database load failed: {db_error}, using demo data")
            # Fall back to demo data from sample_data.py
            from ..sample_data import OPTIMIZATION_RESULTS
            optimized_df = pd.DataFrame(OPTIMIZATION_RESULTS)

        # Convert column names to uppercase for consistency with UI
        optimized_df.columns = [col.upper() for col in optimized_df.columns]

        # Convert DataFrame to records for storage
        optimization_results = optimized_df.to_dict('records')

        # Generate summary statistics
        summary = generate_optimization_summary(optimized_df, run_id)
        log("✓ Summary generated")

        # Build alert message
        ranged_skus = len(optimized_df[optimized_df['IS_RANGED_RECOMMENDED'] == True]) if 'IS_RANGED_RECOMMENDED' in optimized_df.columns else len(optimized_df)
        total_skus = len(optimized_df)
        total_profit = optimized_df['EXPECTED_MARGIN_WEEKLY'].sum() if 'EXPECTED_MARGIN_WEEKLY' in optimized_df.columns else 0
        
        alert_message = dmc.Text([
            html.B(f"Range Optimization Results: {run_id}"),
            html.Br(),
            f"Optimized {ranged_skus} SKUs in range (of {total_skus} evaluated). ",
            f"Expected weekly profit: ${total_profit:,.2f}",
        ])

        log("✅ Range optimization results loaded successfully")
        return optimization_results, summary, alert_message, "green"

    except Exception as e:
        log(f"❌ Error loading optimization results: {str(e)}")
        import traceback
        traceback.print_exc()

        error_message = f"Error loading optimization results: {str(e)}"
        return [], {}, error_message, "red"


def generate_optimization_summary(df: pd.DataFrame, run_id: str) -> Dict[str, Any]:
    """Generate summary statistics for range optimization results."""
    
    # Use new schema column names (uppercase after conversion)
    ranged_df = df[df['IS_RANGED_RECOMMENDED'] == True] if 'IS_RANGED_RECOMMENDED' in df.columns else df
    
    # Calculate changes using new schema column name
    change_col = 'CHANGE_FROM_CURRENT' if 'CHANGE_FROM_CURRENT' in df.columns else 'CHANGE_TYPE'
    skus_added = len(df[df[change_col] == 'new']) if change_col in df.columns else 0
    skus_removed = len(df[df[change_col] == 'removed']) if change_col in df.columns else 0
    skus_increased = len(df[df[change_col] == 'increased']) if change_col in df.columns else 0
    skus_decreased = len(df[df[change_col] == 'decreased']) if change_col in df.columns else 0
    
    # Calculate private label share (if we had brand data indicating PL)
    pl_brands = ['Coles', 'Woolworths', 'Generic', 'Home Brand']
    total_facings = ranged_df['RECOMMENDED_FACINGS'].sum() if 'RECOMMENDED_FACINGS' in ranged_df.columns else 0
    pl_facings = ranged_df[ranged_df['BRAND'].isin(pl_brands)]['RECOMMENDED_FACINGS'].sum() if 'BRAND' in ranged_df.columns else 0
    pl_share = (pl_facings / total_facings * 100) if total_facings > 0 else 0
    
    # Calculate space utilization (assuming 3600mm shelf for demo)
    shelf_width_mm = 3600  # Metro Large shelf
    pack_width_mm = 170  # Approximate average
    space_used_mm = total_facings * pack_width_mm
    space_utilization = (space_used_mm / shelf_width_mm * 100) if shelf_width_mm > 0 else 0
    
    # Use new schema column name for profit
    profit_col = 'EXPECTED_MARGIN_WEEKLY' if 'EXPECTED_MARGIN_WEEKLY' in ranged_df.columns else 'EXPECTED_WEEKLY_PROFIT'
    total_weekly_profit = ranged_df[profit_col].sum() if profit_col in ranged_df.columns else 0
    
    return {
        'run_id': run_id,
        'total_skus_evaluated': len(df),
        'skus_in_range': len(ranged_df),
        'skus_added': skus_added,
        'skus_removed': skus_removed,
        'skus_facings_increased': skus_increased,
        'skus_facings_decreased': skus_decreased,
        'total_weekly_profit': total_weekly_profit,
        'total_facings': int(total_facings),
        'private_label_share_pct': pl_share,
        'space_utilization_pct': min(space_utilization, 100),  # Cap at 100%
    }


@callback(
    Output("optimization-results-grid", "rowData"),
    Input("optimization-data-store", "data"),
)
def update_optimization_grid(optimization_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update the AG-Grid with optimization results"""
    log(f"CALLBACK: update_optimization_grid - rows: {len(optimization_data) if optimization_data else 0}")
    return optimization_data or []


@callback(
    Output("optimization-summary-cards", "children"),
    Input("optimization-summary-store", "data"),
)
def update_summary_cards(summary_data: Dict[str, Any]):
    """Update the summary statistics cards"""
    log(f"CALLBACK: update_summary_cards - has_data: {bool(summary_data)}")
    if not summary_data:
        return html.Div()
    return create_summary_cards(summary_data)


@callback(
    Output("optimization-charts-container", "children"),
    Input("optimization-data-store", "data"),
)
def update_optimization_charts(optimization_data: List[Dict[str, Any]]):
    """Update the optimization visualization charts"""
    log(f"CALLBACK: update_optimization_charts - rows: {len(optimization_data) if optimization_data else 0}")

    if not optimization_data:
        return html.Div()

    # Convert to DataFrame for charting
    df = pd.DataFrame(optimization_data)
    return create_optimization_charts(df)


@callback(
    Output("optimization-results-grid", "exportDataAsCsv"),
    Input("optimization-csv-button", "n_clicks"),
)
def export_optimization_csv(n_clicks: int) -> bool:
    """Export optimization results to CSV"""
    log(f"CALLBACK: export_optimization_csv - n_clicks: {n_clicks}")
    if n_clicks:
        return True
    return False
