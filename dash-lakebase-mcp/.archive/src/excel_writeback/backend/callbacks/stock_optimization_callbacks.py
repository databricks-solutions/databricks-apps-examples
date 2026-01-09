"""Callbacks for Stock Optimization page"""

import datetime
from typing import Dict, Any, List, Tuple
from urllib.parse import parse_qs, urlparse
import pandas as pd
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, html

# ML imports are done within functions to avoid circular imports
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
def populate_forecast_dropdown(_: str, search: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Populate the forecast dropdown with available forecasts that have optimization results.
    Also auto-select forecast if passed via URL query parameter.
    """
    log(f"CALLBACK: populate_forecast_dropdown - search: {search}")
    
    # Parse query parameters
    forecast_from_url = None
    if search:
        try:
            params = parse_qs(search.lstrip("?"))
            forecast_from_url = params.get("forecast", [None])[0]
            log(f"→ Forecast from URL: {forecast_from_url}")
        except Exception as e:
            log(f"Error parsing URL params: {e}")
    
    try:
        from ..ml.forecast_optimizer import get_all_forecast_ids_with_optimization
        forecast_ids = get_all_forecast_ids_with_optimization()
        log(f"✓ Found {len(forecast_ids)} forecasts with optimization results")
        
        dropdown_data = [{"value": fid, "label": fid} for fid in forecast_ids]
        
        # Auto-select forecast from URL if it exists in the list
        selected_value = None
        if forecast_from_url and forecast_from_url in forecast_ids:
            selected_value = forecast_from_url
            log(f"✓ Auto-selecting forecast from URL: {selected_value}")
        
        return dropdown_data, selected_value
    except Exception as e:
        log(f"❌ Error fetching forecast IDs: {e}")
        return [], None


@callback(
    Output("optimization-data-store", "data"),
    Output("optimization-summary-store", "data"),
    Output("optimization-alert", "children"),
    Output("optimization-alert", "color"),
    Input("optimization-forecast-select", "value"),
    prevent_initial_call=True,
)
def load_optimization_results(forecast_id: str) -> Tuple[List[Dict], Dict, str, str]:
    """
    Load stock optimization results for the selected forecast.

    Returns:
        - Optimization results data
        - Summary statistics
        - Alert message
        - Alert color
    """
    log(f"CALLBACK: load_optimization_results - forecast_id: {forecast_id}")

    if not forecast_id:
        return [], {}, "Select a forecast run to view optimization results.", "blue"

    try:
        log(f"→ Loading optimization results for forecast: {forecast_id}")
        from ..ml.forecast_optimizer import get_optimization_results
        from ..ml.mlflow_client import HybridStockOptimizer

        # Fetch optimization results from database
        optimized_df = get_optimization_results(forecast_id)

        if optimized_df.empty:
            log(f"⚠️ No optimization results found for forecast: {forecast_id}")
            return [], {}, f"No optimization results found for forecast {forecast_id}", "yellow"

        log(f"✓ Found {len(optimized_df)} optimization results")

        # Convert column names to uppercase for consistency with UI
        optimized_df.columns = [col.upper() for col in optimized_df.columns]

        # Convert DataFrame to records for storage
        optimization_results = optimized_df.to_dict('records')

        # Generate summary statistics
        optimizer = HybridStockOptimizer()
        summary = optimizer.get_optimization_summary(optimized_df)
        log("✓ Summary generated")

        # Get optimization method from the data
        method_used = optimized_df['OPTIMIZATION_METHOD'].iloc[0] if 'OPTIMIZATION_METHOD' in optimized_df.columns else 'unknown'

        alert_message = dmc.Text([
            html.B(f"Optimization Results for {forecast_id}"),
            html.Br(),
            f"Optimized inventory for {len(optimized_df)} products using {method_used} method. ",
            f"Total annual profit potential: ${summary['total_annual_profit']:,.2f}",
        ])

        log("✅ Stock optimization results loaded successfully")
        return optimization_results, summary, alert_message, "green"

    except Exception as e:
        log(f"❌ Error loading optimization results: {str(e)}")
        import traceback
        traceback.print_exc()

        error_message = f"Error loading optimization results: {str(e)}"
        return [], {}, error_message, "red"


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
