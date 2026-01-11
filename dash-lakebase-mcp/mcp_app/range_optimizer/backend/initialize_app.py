"""
Application Initialization Module

Automatically initializes database tables with sample data on app startup
if they are empty. This ensures the app has data to display on first run.
"""

import pandas as pd
from typing import Dict, Any

from .config import db_config

from .database import (
    check_table_exists,
    query_df,
    bulk_insert,
    create_table_from_dataframe,
)
from .sample_data import INITIAL_DATA
from .logger import logger


def log(msg: str):
    """Simple log wrapper"""
    logger.info(msg)


def initialize_tables_on_startup():
    """
    Initialize database tables with sample data if they are empty.
    Called automatically when the app starts.
    """
    log("=" * 70)
    log("🚀 CHECKING DATABASE INITIALIZATION")
    log("=" * 70)
    
    # Define tables to initialize
    tables_to_check = {
        'layout_data': INITIAL_DATA,
    }
    
    for table_name, sample_data in tables_to_check.items():
        try:
            full_table_name = db_config.get_full_table_name(table_name)
            log(f"📊 Checking table: {full_table_name}")
            
            # Check if table exists
            if not check_table_exists(full_table_name):
                log(f"  ⚠️  Table '{full_table_name}' does not exist")
                log(f"  ➕ Creating table and inserting sample data...")
                
                # Create DataFrame from sample data
                df = pd.DataFrame(sample_data)
                
                # Create table and insert data
                result = bulk_insert(full_table_name, df, overwrite=True)
                
                if isinstance(result, int):
                    log(f"  ✅ Created table '{full_table_name}' with {result} rows")
                else:
                    log(f"  ❌ Failed to create table: {result}")
                
            else:
                # Table exists, check if it's empty
                log(f"  ✓  Table '{full_table_name}' exists")
                
                # Count rows
                count_query = f"SELECT COUNT(*) as count FROM {full_table_name}"
                count_df = query_df(count_query)
                
                if not count_df.empty:
                    row_count = count_df.iloc[0]['count']
                    log(f"  📈 Current row count: {row_count}")
                    
                    if row_count == 0:
                        log(f"  ⚠️  Table is empty, inserting sample data...")
                        
                        # Insert sample data
                        df = pd.DataFrame(sample_data)
                        result = bulk_insert(full_table_name, df, overwrite=False)
                        
                        if isinstance(result, int):
                            log(f"  ✅ Inserted {result} rows into '{full_table_name}'")
                        else:
                            log(f"  ❌ Failed to insert data: {result}")
                    else:
                        log(f"  ✓  Table has data, skipping initialization")
                        
        except Exception as e:
            log(f"❌ Error initializing table '{table_name}': {e}")
            import traceback
            traceback.print_exc()
            # Continue with other tables even if one fails
            continue
    
    log("=" * 70)
    log("✅ DATABASE INITIALIZATION COMPLETE")
    log("=" * 70)


def get_table_stats() -> Dict[str, Any]:
    """
    Get statistics about initialized tables.
    
    Returns:
        dict: Table statistics including row counts
    """
    stats = {}
    
    tables = ['layout_data']
    
    for table_name in tables:
        try:
            full_table_name = db_config.get_full_table_name(table_name)
            
            if check_table_exists(full_table_name):
                count_query = f"SELECT COUNT(*) as count FROM {full_table_name}"
                count_df = query_df(count_query)
                
                if not count_df.empty:
                    stats[table_name] = {
                        'exists': True,
                        'row_count': int(count_df.iloc[0]['count'])
                    }
                else:
                    stats[table_name] = {'exists': True, 'row_count': 0}
            else:
                stats[table_name] = {'exists': False, 'row_count': 0}
                
        except Exception as e:
            stats[table_name] = {'exists': False, 'error': str(e)}
    
    return stats


if __name__ == "__main__":
    # Allow running this module directly for manual initialization
    print("🔧 Manual Database Initialization")
    print("=" * 70)
    initialize_tables_on_startup()
    print("\n📊 Table Statistics:")
    print("=" * 70)
    stats = get_table_stats()
    for table, info in stats.items():
        if info.get('exists'):
            print(f"  • {table}: {info.get('row_count', 0)} rows")
        else:
            print(f"  • {table}: NOT FOUND")
            if 'error' in info:
                print(f"    Error: {info['error']}")

