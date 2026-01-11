"""
Range Optimization Integration

This module provides functions to retrieve and manage optimization results
from the opt_recommended_planogram table.
"""

import pandas as pd
import datetime
from typing import Dict, List, Tuple
from ..database import query_df, bulk_insert
from ..config import db_config


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def get_optimization_results(run_id: str) -> pd.DataFrame:
    """
    Retrieve range optimization results for a given run ID.

    Args:
        run_id: The optimization run ID (OPT-* format)

    Returns:
        DataFrame with planogram recommendations (empty if table doesn't exist)
    """
    try:
        # Use opt_recommended_planogram table from new schema
        results_table = db_config.opt_planogram_table
        query = f'SELECT * FROM {results_table} WHERE optimization_run_id = %s'
        
        df = query_df(query, (run_id,))
        
        if df.empty:
            log(f"No optimization results found for run: {run_id}")
            return df
        
        log(f"Found {len(df)} optimization results for run: {run_id}")
        
        # Convert column names to uppercase for UI consistency
        df.columns = [col.upper() for col in df.columns]
        
        return df
    except Exception as e:
        if "does not exist" in str(e):
            log(f"Results table not yet created - no results available")
        else:
            log(f"Error fetching optimization results: {e}")
        return pd.DataFrame()


def get_all_forecast_ids_with_optimization() -> List[str]:
    """
    Get list of all optimization run IDs that have results.
    
    Queries the opt_recommended_planogram table for distinct run IDs.
    Falls back gracefully if tables don't exist yet.

    Returns:
        List of optimization run IDs (OPT-* format)
    """
    # Try opt_recommended_planogram first
    try:
        results_table = db_config.opt_planogram_table
        query = f'''
            SELECT DISTINCT optimization_run_id, MAX(optimization_run_date) as latest_date 
            FROM {results_table} 
            GROUP BY optimization_run_id 
            ORDER BY latest_date DESC 
            LIMIT 50
        '''
        df = query_df(query)
        if not df.empty:
            run_ids = df['optimization_run_id'].tolist()
            log(f"Found {len(run_ids)} optimization runs in results table")
            return run_ids
    except Exception as e:
        # Table might not exist yet - this is OK on first run
        if "does not exist" in str(e):
            log(f"Results table not yet created (this is normal on first run)")
        else:
            log(f"Error querying results table: {e}")
    
    # Fallback: check optimization_runs table for pending runs
    try:
        runs_table = db_config.optimization_runs_table
        fallback_query = f'''
            SELECT DISTINCT "RUN_ID", MAX("SUBMISSION_TIMESTAMP") as latest_timestamp 
            FROM {runs_table} 
            GROUP BY "RUN_ID" 
            ORDER BY latest_timestamp DESC 
            LIMIT 50
        '''
        df = query_df(fallback_query)
        if not df.empty:
            run_ids = df['RUN_ID'].tolist()
            log(f"Found {len(run_ids)} optimization runs in runs table (pending)")
            return run_ids
    except Exception as e:
        if "does not exist" in str(e):
            log(f"Optimization runs table not yet created (this is normal on first run)")
        else:
            log(f"Error querying runs table: {e}")
    
    log("No optimization runs found - tables may not exist yet")
    return []


def get_optimization_summary(run_id: str) -> Dict:
    """
    Get summary statistics for an optimization run.
    
    Args:
        run_id: The optimization run ID
        
    Returns:
        Dictionary with summary statistics
    """
    results_table = db_config.opt_planogram_table
    
    query = f'''
        SELECT 
            COUNT(*) as sku_count,
            SUM(CASE WHEN is_ranged_recommended THEN 1 ELSE 0 END) as skus_ranged,
            SUM(recommended_facings) as total_facings,
            SUM(expected_margin_weekly) as total_weekly_profit,
            SUM(CASE WHEN change_from_current = 'new' THEN 1 ELSE 0 END) as skus_added,
            SUM(CASE WHEN change_from_current = 'removed' THEN 1 ELSE 0 END) as skus_removed,
            SUM(CASE WHEN change_from_current = 'increased' THEN 1 ELSE 0 END) as skus_increased,
            SUM(CASE WHEN change_from_current = 'decreased' THEN 1 ELSE 0 END) as skus_decreased
        FROM {results_table}
        WHERE optimization_run_id = %s
    '''
    
    try:
        df = query_df(query, (run_id,))
        if df.empty:
            return {}
        
        row = df.iloc[0]
        return {
            'run_id': run_id,
            'total_skus_evaluated': int(row['sku_count'] or 0),
            'skus_in_range': int(row['skus_ranged'] or 0),
            'total_facings': int(row['total_facings'] or 0),
            'total_weekly_profit': float(row['total_weekly_profit'] or 0),
            'skus_added': int(row['skus_added'] or 0),
            'skus_removed': int(row['skus_removed'] or 0),
            'skus_facings_increased': int(row['skus_increased'] or 0),
            'skus_facings_decreased': int(row['skus_decreased'] or 0),
        }
    except Exception as e:
        log(f"Error getting optimization summary: {e}")
        return {}
