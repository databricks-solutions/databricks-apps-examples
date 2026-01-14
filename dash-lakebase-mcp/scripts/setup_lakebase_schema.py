"""
Setup Complete Schema in Lakebase (PostgreSQL)

This script creates the full star schema in Lakebase to support both:
1. Operational data store for real-time app operations
2. Source for replication to Unity Catalog for ML/analytics

Usage:
    uv run python scripts/setup_lakebase_schema.py --load-sample-data

Environment variables required:
    LAKEBASE_INSTANCE_NAME or PGHOST
    LAKEBASE_DATABASE or PGDATABASE
    LAKEBASE_SCHEMA (default: range_optimizer)
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_app"))

from range_optimizer.backend.config import db_config
from range_optimizer.backend.database import execute_sql, query_df, check_table_exists, bulk_insert
from range_optimizer.backend.logger import logger
import pandas as pd
from datetime import datetime, timedelta
import numpy as np


# Schema DDL statements
SCHEMA_DDL = {
    "dim_sku": """
        CREATE TABLE IF NOT EXISTS {schema}.dim_sku (
            sku_id VARCHAR(50) PRIMARY KEY,
            gtin_ean BIGINT,
            sku_name VARCHAR(255) NOT NULL,
            brand_id VARCHAR(50) NOT NULL,
            manufacturer_id VARCHAR(50),
            category_id VARCHAR(50) NOT NULL,
            subcategory_id VARCHAR(50),
            segment VARCHAR(100),
            pack_size DECIMAL(10,2),
            pack_size_uom VARCHAR(20),
            case_pack_qty INT,
            pack_width_mm DECIMAL(10,2),
            pack_depth_mm DECIMAL(10,2),
            pack_height_mm DECIMAL(10,2),
            pack_type VARCHAR(50),
            shelf_life_days INT,
            is_private_label BOOLEAN DEFAULT FALSE,
            is_chilled BOOLEAN DEFAULT FALSE,
            is_frozen BOOLEAN DEFAULT FALSE,
            sku_status VARCHAR(20),
            launch_date DATE,
            discontinue_date DATE,
            weekly_units INT,
            unit_price DECIMAL(10,2),
            unit_cost DECIMAL(10,2),
            gross_margin_pct DECIMAL(5,2),
            current_facings INT,
            is_must_stock BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "dim_store": """
        CREATE TABLE IF NOT EXISTS {schema}.dim_store (
            store_id VARCHAR(50) PRIMARY KEY,
            store_name VARCHAR(255) NOT NULL,
            store_code VARCHAR(50) NOT NULL UNIQUE,
            store_format VARCHAR(50),
            store_size_sqm INT,
            region_id VARCHAR(50),
            region_name VARCHAR(100),
            city VARCHAR(100),
            postcode VARCHAR(20),
            country VARCHAR(50),
            affluence_segment VARCHAR(50),
            demographic_profile VARCHAR(100),
            opening_date DATE,
            closing_date DATE,
            planogram_cluster_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "dim_category": """
        CREATE TABLE IF NOT EXISTS {schema}.dim_category (
            category_id VARCHAR(50) PRIMARY KEY,
            category_name VARCHAR(255) NOT NULL UNIQUE,
            department VARCHAR(100),
            parent_category_id VARCHAR(50),
            category_role VARCHAR(50),
            space_priority INT,
            is_chill_category BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "dim_brand": """
        CREATE TABLE IF NOT EXISTS {schema}.dim_brand (
            brand_id VARCHAR(50) PRIMARY KEY,
            brand_name VARCHAR(255) NOT NULL UNIQUE,
            manufacturer_id VARCHAR(50),
            brand_country VARCHAR(50),
            is_private_label BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "fact_sales_weekly": """
        CREATE TABLE IF NOT EXISTS {schema}.fact_sales_weekly (
            sale_id VARCHAR(50) PRIMARY KEY,
            store_id VARCHAR(50) NOT NULL,
            sku_id VARCHAR(50) NOT NULL,
            week_start_date DATE NOT NULL,
            units_sold INT DEFAULT 0,
            net_sales_value DECIMAL(15,2) DEFAULT 0,
            regular_price DECIMAL(10,2),
            promo_price DECIMAL(10,2),
            promo_flag BOOLEAN DEFAULT FALSE,
            promo_type VARCHAR(50),
            promo_discount_pct DECIMAL(5,2),
            on_display_flag BOOLEAN DEFAULT FALSE,
            on_promotion_flag BOOLEAN DEFAULT FALSE,
            availability_rate DECIMAL(5,2),
            out_of_stock_days INT,
            stock_at_week_start INT,
            stock_at_week_end INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "ml_demand_forecast": """
        CREATE TABLE IF NOT EXISTS {schema}.ml_demand_forecast (
            forecast_id VARCHAR(50) PRIMARY KEY,
            store_id VARCHAR(50),
            planogram_cluster_id VARCHAR(50),
            sku_id VARCHAR(50) NOT NULL,
            forecast_week_start_date DATE,
            baseline_demand_units INT,
            demand_with_promo_units INT,
            demand_with_space_units INT,
            forecast_accuracy_mape DECIMAL(5,2),
            model_version VARCHAR(50),
            model_run_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "opt_recommended_planogram": """
        CREATE TABLE IF NOT EXISTS {schema}.opt_recommended_planogram (
            opt_planogram_id VARCHAR(50) PRIMARY KEY,
            optimization_run_id VARCHAR(50) NOT NULL,
            store_id VARCHAR(50),
            planogram_cluster_id VARCHAR(50),
            category_id VARCHAR(50) NOT NULL,
            sku_id VARCHAR(50) NOT NULL,
            is_ranged_recommended BOOLEAN,
            recommended_facings INT DEFAULT 0,
            recommended_shelf_level INT,
            recommended_position_order INT,
            expected_units_weekly INT,
            expected_sales_value_weekly DECIMAL(15,2),
            expected_margin_weekly DECIMAL(15,2),
            change_from_current VARCHAR(50),
            facings_change INT,
            execution_difficulty VARCHAR(20),
            optimization_run_date DATE,
            valid_from_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    
    "opt_optimization_run_summary": """
        CREATE TABLE IF NOT EXISTS {schema}.opt_optimization_run_summary (
            optimization_run_id VARCHAR(50) PRIMARY KEY,
            run_name VARCHAR(255),
            scenario_type VARCHAR(50),
            stores_included INT,
            categories_included INT,
            clusters_optimized INT,
            objective_value DECIMAL(20,2),
            total_expected_revenue DECIMAL(20,2),
            total_expected_margin DECIMAL(20,2),
            changes_sku_adds INT,
            changes_sku_removes INT,
            changes_sku_facings_changes INT,
            solver_name VARCHAR(50),
            solver_status VARCHAR(50),
            solver_time_seconds DECIMAL(10,2),
            model_version VARCHAR(50),
            run_timestamp TIMESTAMP NOT NULL,
            run_date DATE,
            created_by VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}


def create_schema():
    """Create all tables in Lakebase schema"""
    schema = db_config.schema_name
    
    logger.info("="*70)
    logger.info("🏗️  CREATING LAKEBASE SCHEMA")
    logger.info("="*70)
    logger.info(f"Schema: {schema}")
    logger.info(f"Host: {db_config.host}")
    logger.info(f"Database: {db_config.database}")
    logger.info("")
    
    # Create schema if it doesn't exist
    execute_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    logger.info(f"✅ Created schema: {schema}")
    logger.info("")
    
    # Create tables
    for table_name, ddl in SCHEMA_DDL.items():
        try:
            full_table_name = f"{schema}.{table_name}"
            
            # Check if table exists
            if check_table_exists(full_table_name):
                logger.info(f"⏭️  Table already exists: {full_table_name}")
                continue
            
            # Create table
            execute_sql(ddl.format(schema=schema))
            logger.info(f"✅ Created table: {full_table_name}")
            
        except Exception as e:
            logger.error(f"❌ Error creating table {table_name}: {e}")
            raise
    
    logger.info("")
    logger.info("="*70)
    logger.info("✅ SCHEMA CREATION COMPLETE")
    logger.info("="*70)


def load_sample_data():
    """Load sample data into Lakebase tables"""
    schema = db_config.schema_name
    
    logger.info("="*70)
    logger.info("📊 LOADING SAMPLE DATA")
    logger.info("="*70)
    
    now = datetime.now()
    
    # Sample Categories
    categories = [
        {"category_id": "CAT001", "category_name": "Beer & Seltzer", "department": "Liquor", 
         "parent_category_id": None, "category_role": "destination", "space_priority": 2, 
         "is_chill_category": True, "created_at": now, "updated_at": now},
        {"category_id": "CAT002", "category_name": "Hot Sauce", "department": "Grocery", 
         "parent_category_id": None, "category_role": "routine", "space_priority": 3, 
         "is_chill_category": False, "created_at": now, "updated_at": now},
        {"category_id": "CAT003", "category_name": "Ice Cream", "department": "Frozen", 
         "parent_category_id": None, "category_role": "destination", "space_priority": 1, 
         "is_chill_category": False, "created_at": now, "updated_at": now},
    ]
    
    # Sample Brands
    brands = [
        {"brand_id": "BRD001", "brand_name": "Stone & Wood", "manufacturer_id": "MFG001", 
         "brand_country": "Australia", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD002", "brand_name": "Balter", "manufacturer_id": "MFG002", 
         "brand_country": "Australia", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD003", "brand_name": "White Claw", "manufacturer_id": "MFG003", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD010", "brand_name": "Sriracha", "manufacturer_id": "MFG010", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD011", "brand_name": "Tabasco", "manufacturer_id": "MFG011", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD012", "brand_name": "Cholula", "manufacturer_id": "MFG012", 
         "brand_country": "Mexico", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD020", "brand_name": "Ben & Jerry's", "manufacturer_id": "MFG020", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
        {"brand_id": "BRD021", "brand_name": "Häagen-Dazs", "manufacturer_id": "MFG021", 
         "brand_country": "USA", "is_private_label": False, "created_at": now, "updated_at": now},
    ]
    
    # Sample SKUs (subset from sample_data.py)
    skus = [
        {"sku_id": "SKU3001", "sku_name": "Stone & Wood Pacific Ale 6pk", "brand_id": "BRD001", 
         "category_id": "CAT001", "segment": "Craft Beer", "pack_size": 1980, "pack_size_uom": "ml", 
         "pack_width_mm": 180, "weekly_units": 85, "unit_price": 24.00, "unit_cost": 14.40, 
         "gross_margin_pct": 40, "current_facings": 3, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_chilled": True},
        {"sku_id": "SKU3003", "sku_name": "Balter XPA 4pk", "brand_id": "BRD002", 
         "category_id": "CAT001", "segment": "Craft Beer", "pack_size": 1500, "pack_size_uom": "ml", 
         "pack_width_mm": 150, "weekly_units": 95, "unit_price": 22.00, "unit_cost": 13.20, 
         "gross_margin_pct": 40, "current_facings": 3, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_chilled": True},
        {"sku_id": "SKU3009", "sku_name": "White Claw Variety 12pk", "brand_id": "BRD003", 
         "category_id": "CAT001", "segment": "Hard Seltzer", "pack_size": 3960, "pack_size_uom": "ml", 
         "pack_width_mm": 260, "weekly_units": 120, "unit_price": 32.00, "unit_cost": 17.60, 
         "gross_margin_pct": 45, "current_facings": 4, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_chilled": True},
        {"sku_id": "SKU4001", "sku_name": "Sriracha Original 455ml", "brand_id": "BRD010", 
         "category_id": "CAT002", "segment": "Asian Style", "pack_size": 455, "pack_size_uom": "ml", 
         "pack_width_mm": 80, "weekly_units": 145, "unit_price": 6.50, "unit_cost": 2.93, 
         "gross_margin_pct": 55, "current_facings": 4, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_chilled": False},
        {"sku_id": "SKU4003", "sku_name": "Tabasco Original 150ml", "brand_id": "BRD011", 
         "category_id": "CAT002", "segment": "Louisiana Style", "pack_size": 150, "pack_size_uom": "ml", 
         "pack_width_mm": 50, "weekly_units": 110, "unit_price": 5.00, "unit_cost": 2.25, 
         "gross_margin_pct": 55, "current_facings": 3, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_chilled": False},
        {"sku_id": "SKU5001", "sku_name": "Ben & Jerry's Cookie Dough 458ml", "brand_id": "BRD020", 
         "category_id": "CAT003", "segment": "Premium Pints", "pack_size": 458, "pack_size_uom": "ml", 
         "pack_width_mm": 110, "weekly_units": 90, "unit_price": 13.50, "unit_cost": 6.75, 
         "gross_margin_pct": 50, "current_facings": 3, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_frozen": True},
        {"sku_id": "SKU5006", "sku_name": "Häagen-Dazs Vanilla 457ml", "brand_id": "BRD021", 
         "category_id": "CAT003", "segment": "Premium Pints", "pack_size": 457, "pack_size_uom": "ml", 
         "pack_width_mm": 110, "weekly_units": 80, "unit_price": 14.00, "unit_cost": 7.00, 
         "gross_margin_pct": 50, "current_facings": 2, "is_private_label": False, 
         "is_must_stock": True, "sku_status": "active", "is_frozen": True},
    ]
    
    # Sample Stores
    stores = [
        {"store_id": "STORE001", "store_name": "Coles Docklands", "store_code": "COL-001", 
         "store_format": "supermarket", "store_size_sqm": 2500, "region_id": "REG001", 
         "region_name": "Victoria", "city": "Melbourne", "postcode": "3008", 
         "country": "Australia", "affluence_segment": "high", 
         "demographic_profile": "urban professionals", "opening_date": "2020-01-15", 
         "closing_date": None, "planogram_cluster_id": "CLUSTER001", 
         "created_at": now, "updated_at": now},
    ]
    
    # Load data
    try:
        # Categories
        cat_df = pd.DataFrame(categories)
        result = bulk_insert(f"{schema}.dim_category", cat_df, overwrite=True)
        logger.info(f"✅ Loaded {len(categories)} categories")
        
        # Brands
        brand_df = pd.DataFrame(brands)
        result = bulk_insert(f"{schema}.dim_brand", brand_df, overwrite=True)
        logger.info(f"✅ Loaded {len(brands)} brands")
        
        # SKUs
        sku_df = pd.DataFrame(skus)
        sku_df['manufacturer_id'] = sku_df['brand_id'].str.replace('BRD', 'MFG')
        sku_df['created_at'] = now
        sku_df['updated_at'] = now
        result = bulk_insert(f"{schema}.dim_sku", sku_df, overwrite=True)
        logger.info(f"✅ Loaded {len(skus)} SKUs")
        
        # Stores
        store_df = pd.DataFrame(stores)
        result = bulk_insert(f"{schema}.dim_store", store_df, overwrite=True)
        logger.info(f"✅ Loaded {len(stores)} stores")
        
        # Generate sales data (last 12 weeks)
        logger.info("📊 Generating sample sales data...")
        sales_data = []
        sale_id = 1
        for week_offset in range(12):
            week_start = datetime.now().date() - timedelta(weeks=12-week_offset)
            for store in stores:
                for sku in skus:
                    base_units = sku["weekly_units"]
                    variance = np.random.normal(1.0, 0.15)
                    units_sold = max(0, int(base_units * variance))
                    
                    sales_data.append({
                        "sale_id": f"SALE{sale_id:08d}",
                        "store_id": store["store_id"],
                        "sku_id": sku["sku_id"],
                        "week_start_date": week_start,
                        "units_sold": units_sold,
                        "net_sales_value": units_sold * sku["unit_price"],
                        "regular_price": sku["unit_price"],
                        "promo_flag": False,
                        "availability_rate": 98.0,
                        "created_at": now,
                        "updated_at": now
                    })
                    sale_id += 1
        
        sales_df = pd.DataFrame(sales_data)
        result = bulk_insert(f"{schema}.fact_sales_weekly", sales_df, overwrite=True)
        logger.info(f"✅ Loaded {len(sales_data)} sales records (12 weeks)")
        
        # Generate demand forecasts
        logger.info("📈 Generating demand forecasts...")
        forecast_data = []
        for sku in skus:
            forecast_data.append({
                "forecast_id": f"FCST_{sku['sku_id']}",
                "planogram_cluster_id": "CLUSTER001",
                "sku_id": sku["sku_id"],
                "forecast_week_start_date": datetime.now().date(),
                "baseline_demand_units": sku["weekly_units"],
                "demand_with_promo_units": int(sku["weekly_units"] * 1.3),
                "demand_with_space_units": int(sku["weekly_units"] * 1.1),
                "forecast_accuracy_mape": round(np.random.uniform(8, 15), 2),
                "model_version": "v1.0",
                "model_run_date": datetime.now().date(),
                "created_at": now
            })
        
        forecast_df = pd.DataFrame(forecast_data)
        result = bulk_insert(f"{schema}.ml_demand_forecast", forecast_df, overwrite=True)
        logger.info(f"✅ Loaded {len(forecast_data)} demand forecasts")
        
    except Exception as e:
        logger.error(f"❌ Error loading sample data: {e}")
        raise
    
    logger.info("")
    logger.info("="*70)
    logger.info("✅ SAMPLE DATA LOADING COMPLETE")
    logger.info("="*70)


def verify_schema():
    """Verify schema and print table statistics"""
    schema = db_config.schema_name
    
    logger.info("="*70)
    logger.info("📊 SCHEMA VERIFICATION")
    logger.info("="*70)
    
    for table_name in SCHEMA_DDL.keys():
        try:
            full_table_name = f"{schema}.{table_name}"
            
            if check_table_exists(full_table_name):
                count_df = query_df(f"SELECT COUNT(*) as count FROM {full_table_name}")
                row_count = count_df.iloc[0]['count'] if not count_df.empty else 0
                logger.info(f"  {table_name:40} {row_count:>8,} rows")
            else:
                logger.info(f"  {table_name:40} NOT FOUND")
                
        except Exception as e:
            logger.info(f"  {table_name:40} ERROR: {e}")
    
    logger.info("="*70)


def main():
    parser = argparse.ArgumentParser(description="Setup Lakebase schema for Range Optimizer")
    parser.add_argument("--load-sample-data", action="store_true", 
                       help="Load sample data after creating schema")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify existing schema (don't create or load)")
    
    args = parser.parse_args()
    
    try:
        if args.verify_only:
            verify_schema()
        else:
            create_schema()
            
            if args.load_sample_data:
                load_sample_data()
            
            verify_schema()
        
        logger.info("")
        logger.info("🎉 Setup complete!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run: databricks jobs run-now --job-name 'Replicate Lakebase to Delta'")
        logger.info("  2. Run: databricks jobs run-now --job-name 'Create Feature Tables'")
        logger.info("  3. Run: databricks jobs run-now --job-name 'Train Stock Optimizer'")
        
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
