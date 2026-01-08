#!/usr/bin/env python3
"""
Utility script to regenerate stock optimizations for existing forecasts.

This script is useful when:
1. Forecasts were submitted but optimization failed
2. You want to re-run optimization with updated parameters
3. You need to backfill optimization results for historical forecasts

Usage:
    # Regenerate for a specific forecast ID
    python regenerate_optimizations.py FCST-20260108-5fe6f0af
    
    # Regenerate for all forecasts that are missing optimizations
    python regenerate_optimizations.py --all-missing
    
    # Regenerate for all forecasts (force overwrite)
    python regenerate_optimizations.py --all --force
"""

import sys
import argparse
from typing import List
import pandas as pd

from src.dash_dbx_writeback.database_operations import query_df, execute_sql
from src.dash_dbx_writeback.ml.forecast_optimizer import (
    run_stock_optimization_for_forecast,
    get_all_forecast_ids_with_optimization,
)
from src.dash_dbx_writeback.config import db_config


def log(message: str) -> None:
    """Print a log message"""
    print(f"[regenerate_optimizations] {message}")


def get_all_forecast_ids() -> List[str]:
    """Get all forecast IDs from the forecast_submissions table."""
    submissions_table = db_config.get_full_table_name("forecast_submissions")
    query = f'SELECT DISTINCT "FORECAST_ID" FROM {submissions_table} ORDER BY "FORECAST_ID" DESC'
    
    try:
        df = query_df(query)
        return df['FORECAST_ID'].tolist() if not df.empty else []
    except Exception as e:
        log(f"Error fetching forecast IDs: {e}")
        return []


def get_forecast_ids_missing_optimization() -> List[str]:
    """Get forecast IDs that don't have optimization results."""
    all_forecasts = set(get_all_forecast_ids())
    forecasts_with_optimization = set(get_all_forecast_ids_with_optimization())
    
    missing = all_forecasts - forecasts_with_optimization
    return sorted(list(missing), reverse=True)


def delete_optimization_results(forecast_id: str) -> bool:
    """Delete existing optimization results for a forecast ID."""
    results_table = db_config.get_full_table_name("stock_optimization_results")
    delete_query = f'DELETE FROM {results_table} WHERE forecast_id = %s'
    
    try:
        return execute_sql(delete_query, (forecast_id,))
    except Exception as e:
        log(f"Error deleting optimization results: {e}")
        return False


def regenerate_optimization(forecast_id: str, force: bool = False) -> bool:
    """
    Regenerate stock optimization for a forecast ID.
    
    Args:
        forecast_id: The forecast ID to regenerate optimization for
        force: If True, delete existing optimization results first
        
    Returns:
        bool: True if successful, False otherwise
    """
    log(f"{'='*60}")
    log(f"Processing forecast: {forecast_id}")
    
    # Check if optimization already exists
    forecasts_with_optimization = get_all_forecast_ids_with_optimization()
    has_optimization = forecast_id in forecasts_with_optimization
    
    if has_optimization and not force:
        log(f"⚠️  Optimization already exists for {forecast_id}. Use --force to overwrite.")
        return False
    
    # Delete existing optimization if force is True
    if has_optimization and force:
        log(f"→ Deleting existing optimization results...")
        if not delete_optimization_results(forecast_id):
            log(f"❌ Failed to delete existing optimization results")
            return False
        log(f"✓ Deleted existing optimization results")
    
    # Run optimization
    try:
        log(f"→ Running stock optimization...")
        optimized_df, method_used = run_stock_optimization_for_forecast(forecast_id)
        log(f"✅ Successfully optimized {len(optimized_df)} products using '{method_used}' method")
        return True
    except Exception as e:
        log(f"❌ Failed to generate optimization: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate stock optimizations for existing forecasts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'forecast_ids',
        nargs='*',
        help='Specific forecast IDs to regenerate (e.g., FCST-20260108-5fe6f0af)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Regenerate for all forecasts'
    )
    
    parser.add_argument(
        '--all-missing',
        action='store_true',
        help='Regenerate only for forecasts missing optimization results'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite of existing optimization results'
    )
    
    args = parser.parse_args()
    
    # Determine which forecast IDs to process
    forecast_ids_to_process = []
    
    if args.all:
        log("→ Getting all forecast IDs...")
        forecast_ids_to_process = get_all_forecast_ids()
        log(f"Found {len(forecast_ids_to_process)} forecasts")
    elif args.all_missing:
        log("→ Getting forecast IDs missing optimization...")
        forecast_ids_to_process = get_forecast_ids_missing_optimization()
        log(f"Found {len(forecast_ids_to_process)} forecasts missing optimization")
    elif args.forecast_ids:
        forecast_ids_to_process = args.forecast_ids
        log(f"Processing {len(forecast_ids_to_process)} specified forecast(s)")
    else:
        parser.print_help()
        sys.exit(1)
    
    if not forecast_ids_to_process:
        log("No forecasts to process")
        return
    
    # Process each forecast
    log(f"\n{'='*60}")
    log(f"Starting regeneration of {len(forecast_ids_to_process)} forecast(s)")
    log(f"Force mode: {args.force}")
    log(f"{'='*60}\n")
    
    success_count = 0
    failure_count = 0
    skipped_count = 0
    
    for forecast_id in forecast_ids_to_process:
        result = regenerate_optimization(forecast_id, force=args.force)
        
        if result:
            success_count += 1
        elif result is False and not args.force:
            skipped_count += 1
        else:
            failure_count += 1
        
        print()  # Blank line between forecasts
    
    # Summary
    log(f"{'='*60}")
    log(f"SUMMARY")
    log(f"{'='*60}")
    log(f"Total processed:  {len(forecast_ids_to_process)}")
    log(f"✅ Successful:    {success_count}")
    log(f"❌ Failed:        {failure_count}")
    log(f"⏭️  Skipped:       {skipped_count}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()

