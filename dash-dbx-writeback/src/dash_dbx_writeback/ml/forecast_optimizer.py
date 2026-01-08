"""
Forecast Optimization Integration

This module integrates stock optimization with forecast submissions.
"""

import pandas as pd
import datetime
from typing import Dict, List, Tuple
from ..database_operations import query_df, bulk_insert
from ..config import db_config
from .mlflow_client import HybridStockOptimizer


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def run_stock_optimization_for_forecast(forecast_id: str) -> Tuple[pd.DataFrame, str]:
    """
    Run stock optimization for a submitted forecast.

    Args:
        forecast_id: The forecast ID to optimize

    Returns:
        Tuple of (optimization results DataFrame, method used)
    """
    log(f"→ Running stock optimization for forecast: {forecast_id}")

    try:
        # 1. Fetch forecast submission data
        submission_table = db_config.get_full_table_name("forecast_submissions")
        query = f'SELECT * FROM {submission_table} WHERE "FORECAST_ID" = %s'

        log(f"→ Fetching forecast data from {submission_table}")
        forecast_df = query_df(query, (forecast_id,))

        if forecast_df.empty:
            raise ValueError(f"No forecast data found for ID: {forecast_id}")

        log(f"✓ Found {len(forecast_df)} products in forecast")

        # 2. Transform forecast data for optimization
        # Generate dummy sales forecasts based on the product data
        log("→ Generating sales forecast data...")

        forecast_data = []
        for _, row in forecast_df.iterrows():
            # Use shelf space as a proxy for demand
            # In production, this would come from actual forecast results
            base_demand = float(row.get('SHELF_SPACE_CM', 10)) * 10

            forecast_data.append({
                'SELL_ID': row['SELL_ID'],
                'PRODUCT_NAME': row.get('PRODUCT_NAME', 'Unknown'),
                'AVG_DAILY_DEMAND': base_demand,
                'DEMAND_STD': base_demand * 0.2,  # 20% std deviation
                'TOTAL_FORECAST_30D': base_demand * 30,
                'UNIT_COST': 10.0,  # Dummy cost
                'SELLING_PRICE': 20.0,  # Dummy price
                'CATEGORY_NAME': row.get('CATEGORY_NAME', 'Unknown'),
                'SUBCATEGORY_NAME': row.get('SUBCATEGORY_NAME', 'Unknown'),
            })

        optimization_input_df = pd.DataFrame(forecast_data)
        log(f"✓ Prepared optimization input for {len(optimization_input_df)} products")

        # 3. Run optimization
        log("→ Initializing optimizer...")
        optimizer = HybridStockOptimizer(
            endpoint_name="stock-optimization-model",
            use_fallback=True
        )

        log("→ Running optimization...")
        optimized_df, method_used = optimizer.optimize(optimization_input_df)
        log(f"✓ Optimization complete using '{method_used}' method")

        # 4. Add forecast metadata and convert column names to lowercase for PostgreSQL
        optimized_df['forecast_id'] = forecast_id
        optimized_df['optimization_timestamp'] = datetime.datetime.now().isoformat()
        optimized_df['optimization_method'] = method_used

        # Add category information
        category_map = optimization_input_df.set_index('SELL_ID')[['CATEGORY_NAME', 'SUBCATEGORY_NAME']].to_dict('index')
        optimized_df['category_name'] = optimized_df['SELL_ID'].map(lambda x: category_map.get(x, {}).get('CATEGORY_NAME', 'Unknown'))
        optimized_df['subcategory_name'] = optimized_df['SELL_ID'].map(lambda x: category_map.get(x, {}).get('SUBCATEGORY_NAME', 'Unknown'))

        # Convert all column names to lowercase for PostgreSQL compatibility
        optimized_df.columns = [col.lower() for col in optimized_df.columns]

        # 5. Save to database
        results_table = db_config.get_full_table_name("stock_optimization_results")
        log(f"→ Saving results to {results_table}")

        result = bulk_insert(results_table, optimized_df, overwrite=False)
        log(f"✓ Saved {result} optimization results")

        return optimized_df, method_used

    except Exception as e:
        log(f"❌ Error running stock optimization: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def get_optimization_results(forecast_id: str) -> pd.DataFrame:
    """
    Retrieve stock optimization results for a forecast ID.

    Args:
        forecast_id: The forecast ID

    Returns:
        DataFrame with optimization results
    """
    results_table = db_config.get_full_table_name("stock_optimization_results")
    query = f'SELECT * FROM {results_table} WHERE forecast_id = %s'

    return query_df(query, (forecast_id,))


def get_all_forecast_ids_with_optimization() -> List[str]:
    """
    Get list of all forecast IDs that have optimization results.

    Returns:
        List of forecast IDs
    """
    results_table = db_config.get_full_table_name("stock_optimization_results")
    # Include optimization_timestamp in SELECT so we can ORDER BY it
    query = f'SELECT DISTINCT forecast_id, MAX(optimization_timestamp) as latest_timestamp FROM {results_table} GROUP BY forecast_id ORDER BY latest_timestamp DESC LIMIT 50'

    try:
        df = query_df(query)
        return df['forecast_id'].tolist() if not df.empty else []
    except Exception as e:
        log(f"Error fetching forecast IDs: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        return []
