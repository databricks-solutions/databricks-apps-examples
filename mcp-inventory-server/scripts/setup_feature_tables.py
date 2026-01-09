"""
Setup Feature Tables for Stock Optimization

This script creates the feature tables in Unity Catalog that will be used
for stock optimization feature serving.

Run this script once to set up the feature tables.
"""

import pandas as pd
from databricks.sdk import WorkspaceClient
from server import utils
import datetime


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [SETUP] {message}")


def create_feature_tables():
    """Create feature tables in Unity Catalog"""
    
    log("Starting feature tables setup...")
    
    # SQL to create feature tables (PostgreSQL syntax for Lakebase)
    tables_sql = [
        # Product demand features
        """
        CREATE TABLE IF NOT EXISTS excel_app.product_demand_features (
            sell_id VARCHAR(100) PRIMARY KEY,
            avg_daily_demand DOUBLE PRECISION,
            demand_std DOUBLE PRECISION,
            total_forecast_30d DOUBLE PRECISION,
            seasonal_factor DOUBLE PRECISION,
            trend_factor DOUBLE PRECISION,
            last_updated TIMESTAMP
        )
        """,
        
        # Product cost features
        """
        CREATE TABLE IF NOT EXISTS excel_app.product_cost_features (
            sell_id VARCHAR(100) PRIMARY KEY,
            unit_cost DOUBLE PRECISION,
            selling_price DOUBLE PRECISION,
            holding_cost_rate DOUBLE PRECISION,
            ordering_cost DOUBLE PRECISION,
            last_updated TIMESTAMP
        )
        """,
        
        # Current inventory state
        """
        CREATE TABLE IF NOT EXISTS excel_app.current_inventory (
            sell_id VARCHAR(100) PRIMARY KEY,
            current_stock INTEGER,
            safety_stock INTEGER,
            last_order_date DATE,
            last_updated TIMESTAMP
        )
        """,
    ]
    
    # Execute table creation
    for i, sql in enumerate(tables_sql, 1):
        try:
            log(f"Creating feature table {i}/3...")
            utils.execute_query(sql)
            log(f"✓ Feature table {i}/3 created successfully")
        except Exception as e:
            log(f"⚠️  Table {i} might already exist or error: {e}")
    
    log("✓ Feature tables setup complete!")


def populate_initial_features():
    """Populate feature tables with initial sample data"""
    
    log("Populating initial feature data...")
    
    # Get existing products from layout_data
    query = 'SELECT "SELL_ID" FROM excel_app.layout_data'
    products = utils.execute_query(query)
    
    if not products:
        log("⚠️  No products found in layout_data. Skipping initial population.")
        return
    
    log(f"Found {len(products)} products to initialize")
    
    timestamp = datetime.datetime.now().isoformat()
    
    # Prepare demand features (using historical patterns or estimates)
    demand_features = []
    cost_features = []
    inventory_features = []
    
    for product in products:
        sell_id = product['SELL_ID']
        
        # Generate initial demand features (replace with actual historical analysis)
        base_demand = 50.0  # Default base demand
        demand_features.append({
            'sell_id': sell_id,
            'avg_daily_demand': base_demand,
            'demand_std': base_demand * 0.2,  # 20% std deviation
            'total_forecast_30d': base_demand * 30,
            'seasonal_factor': 1.0,
            'trend_factor': 1.0,
            'last_updated': timestamp
        })
        
        # Generate initial cost features
        cost_features.append({
            'sell_id': sell_id,
            'unit_cost': 10.0,
            'selling_price': 20.0,
            'holding_cost_rate': 0.2,  # 20% annual holding cost
            'ordering_cost': 50.0,
            'last_updated': timestamp
        })
        
        # Generate initial inventory state
        inventory_features.append({
            'sell_id': sell_id,
            'current_stock': 100,
            'safety_stock': int(base_demand * 3),  # 3 days of safety stock
            'last_order_date': datetime.date.today().isoformat(),
            'last_updated': timestamp
        })
    
    # Insert data using batch insert
    try:
        log("→ Inserting demand features...")
        utils.batch_insert('excel_app.product_demand_features', demand_features, overwrite=True)
        log("✓ Demand features inserted")
        
        log("→ Inserting cost features...")
        utils.batch_insert('excel_app.product_cost_features', cost_features, overwrite=True)
        log("✓ Cost features inserted")
        
        log("→ Inserting inventory features...")
        utils.batch_insert('excel_app.current_inventory', inventory_features, overwrite=True)
        log("✓ Inventory features inserted")
        
        log("✓ Initial feature data populated successfully!")
    except Exception as e:
        log(f"❌ Error populating features: {e}")
        import traceback
        traceback.print_exc()


def verify_setup():
    """Verify that feature tables are set up correctly"""
    
    log("Verifying feature tables setup...")
    
    tables = [
        'excel_app.product_demand_features',
        'excel_app.product_cost_features',
        'excel_app.current_inventory'
    ]
    
    all_good = True
    for table in tables:
        try:
            query = f"SELECT COUNT(*) as cnt FROM {table}"
            result = utils.execute_query(query)
            count = result[0]['cnt'] if result else 0
            log(f"✓ {table}: {count} rows")
        except Exception as e:
            log(f"❌ {table}: Error - {e}")
            all_good = False
    
    if all_good:
        log("✅ All feature tables verified successfully!")
    else:
        log("⚠️  Some feature tables have issues")
    
    return all_good


def main():
    """Main setup function"""
    log("=" * 70)
    log("FEATURE TABLES SETUP")
    log("=" * 70)
    
    # Step 1: Create tables
    create_feature_tables()
    
    # Step 2: Populate with initial data
    populate_initial_features()
    
    # Step 3: Verify
    verify_setup()
    
    log("=" * 70)
    log("SETUP COMPLETE!")
    log("=" * 70)
    log("")
    log("Next steps:")
    log("1. Run: uv run python scripts/create_feature_spec.py")
    log("2. Run: uv run python scripts/create_feature_serving_endpoint.py")


if __name__ == "__main__":
    main()

