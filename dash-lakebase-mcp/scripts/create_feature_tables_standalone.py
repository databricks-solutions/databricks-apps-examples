#!/usr/bin/env python3
"""
Standalone script to create Feature Store tables in Unity Catalog.

This script:
1. Reads SKU data from Lakebase PostgreSQL (dim_sku table)
2. Creates Feature Store tables in Unity Catalog:
   - sku_features (static product attributes)
   - demand_features (demand forecasts and volatility)

Usage:
    python scripts/create_feature_tables_standalone.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "mcp_app"))

import pandas as pd
import numpy as np
from datetime import datetime
from databricks.sdk import WorkspaceClient
from databricks.feature_engineering import FeatureEngineeringClient

# Import database config and utilities
from range_optimizer.backend.config import db_config
from range_optimizer.backend.database import query_df, initialize_connection_pool
from range_optimizer.backend.logger import logger

# Configuration
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"
PRODUCT_FEATURES_TABLE = "sku_features"
DEMAND_FEATURES_TABLE = "demand_features"

PRODUCT_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{PRODUCT_FEATURES_TABLE}"
DEMAND_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{DEMAND_FEATURES_TABLE}"


def create_demand_features(sku_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create demand features using WEEKLY_UNITS from Lakebase.

    The Lakebase dim_sku table already has WEEKLY_UNITS - we use that as the base
    and derive forecast metrics from it.
    """
    np.random.seed(42)

    # Category-based demand variation multipliers
    category_variance = {
        'Beer & Seltzer': 0.25,   # Moderate variance
        'Hot Sauce': 0.20,        # Lower variance
        'Ice Cream': 0.35,        # Higher variance (seasonal)
    }

    demand_data = []
    for _, row in sku_df.iterrows():
        # Use WEEKLY_UNITS from Lakebase (already in the data!)
        weekly_units = row.get('WEEKLY_UNITS', 50)
        if pd.isna(weekly_units):
            weekly_units = 50
        weekly_units = float(weekly_units)

        # Calculate standard deviation based on category
        category = row.get('CATEGORY', 'Unknown')
        variance_mult = category_variance.get(category, 0.25)
        demand_std = weekly_units * variance_mult

        # 4-week forecast
        forecast_4w = weekly_units * 4

        demand_data.append({
            'SKU_ID': row['SKU_ID'],
            'WEEKLY_UNITS': round(weekly_units, 2),
            'DEMAND_STD': round(demand_std, 2),
            'FORECAST_4W': round(forecast_4w, 2),
            'FORECAST_DATE': datetime.now().date().isoformat(),
            'LAST_UPDATED': datetime.now().isoformat()
        })

    return pd.DataFrame(demand_data)


def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🎯 Creating Feature Store Tables for Range Optimization")
    logger.info("=" * 80)

    # Initialize database connection
    logger.info("📡 Initializing database connection...")
    if not initialize_connection_pool():
        logger.error("❌ Failed to initialize database connection")
        return 1

    # Initialize Databricks clients
    logger.info("🔧 Initializing Databricks clients...")
    w = WorkspaceClient()
    fe = FeatureEngineeringClient()

    # Get Spark session from Databricks Connect or runtime
    try:
        from databricks.connect import DatabricksSession
        spark = DatabricksSession.builder.getOrCreate()
        logger.info("✅ Using Databricks Connect")
    except ImportError:
        try:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            logger.info("✅ Using local Spark session")
        except Exception as e:
            logger.error(f"❌ Failed to create Spark session: {e}")
            logger.error("   Make sure you're running in a Databricks environment")
            return 1

    # Create catalog and schema
    logger.info(f"📁 Creating catalog and schema...")
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        logger.info(f"✅ Catalog {CATALOG} ready")
    except Exception as e:
        logger.warning(f"⚠️  Catalog creation warning: {e}")

    try:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
        logger.info(f"✅ Schema {CATALOG}.{SCHEMA} ready")
    except Exception as e:
        logger.warning(f"⚠️  Schema creation warning: {e}")

    # Load SKU data from Lakebase
    logger.info("📦 Loading SKU data from Lakebase PostgreSQL...")
    table_name = db_config.get_full_table_name(db_config.TABLE_DIM_SKU)

    try:
        query = f'SELECT * FROM {table_name}'
        sku_df = query_df(query)
        logger.info(f"✅ Loaded {len(sku_df)} SKUs from {table_name}")
    except Exception as e:
        logger.error(f"❌ Failed to load SKU data: {e}")
        logger.info("   Using fallback sample data...")
        sku_df = pd.DataFrame([
            {"SKU_ID": "SKU3001", "SKU_NAME": "Stone & Wood Pacific Ale 6pk", "BRAND": "Stone & Wood",
             "CATEGORY": "Beer & Seltzer", "SEGMENT": "Craft Beer", "PACK_SIZE": "6x330ml",
             "PACK_WIDTH_MM": 180, "UNIT_PRICE": 24.00, "UNIT_COST": 14.40, "GROSS_MARGIN_PCT": 40,
             "WEEKLY_UNITS": 85, "CURRENT_FACINGS": 3, "IS_PRIVATE_LABEL": False,
             "IS_MUST_STOCK": True, "STATUS": "active"},
            {"SKU_ID": "SKU4001", "SKU_NAME": "Sriracha Original 455ml", "BRAND": "Sriracha",
             "CATEGORY": "Hot Sauce", "SEGMENT": "Asian Style", "PACK_SIZE": "455ml",
             "PACK_WIDTH_MM": 80, "UNIT_PRICE": 6.50, "UNIT_COST": 2.93, "GROSS_MARGIN_PCT": 55,
             "WEEKLY_UNITS": 145, "CURRENT_FACINGS": 4, "IS_PRIVATE_LABEL": False,
             "IS_MUST_STOCK": True, "STATUS": "active"},
            {"SKU_ID": "SKU5001", "SKU_NAME": "Ben & Jerry's Cookie Dough 458ml", "BRAND": "Ben & Jerry's",
             "CATEGORY": "Ice Cream", "SEGMENT": "Premium Pints", "PACK_SIZE": "458ml",
             "PACK_WIDTH_MM": 110, "UNIT_PRICE": 13.50, "UNIT_COST": 6.75, "GROSS_MARGIN_PCT": 50,
             "WEEKLY_UNITS": 90, "CURRENT_FACINGS": 3, "IS_PRIVATE_LABEL": False,
             "IS_MUST_STOCK": True, "STATUS": "active"},
        ])

    # Add timestamp if not present
    if 'CREATED_AT' not in sku_df.columns:
        sku_df['CREATED_AT'] = datetime.now().isoformat()

    logger.info(f"📊 SKU data ready: {len(sku_df)} products")

    # Create SKU Features table
    logger.info(f"🔧 Creating SKU Features table: {PRODUCT_FEATURES_PATH}")
    try:
        sku_features_spark = spark.createDataFrame(sku_df)

        # Drop existing table
        spark.sql(f"DROP TABLE IF EXISTS {PRODUCT_FEATURES_PATH}")

        # Create feature table
        fe.create_table(
            name=PRODUCT_FEATURES_PATH,
            primary_keys=["SKU_ID"],
            df=sku_features_spark,
            description="SKU features for range optimization including costs, categories, and shelf space allocation"
        )
        logger.info(f"✅ Created SKU Features table with {len(sku_df)} SKUs")
    except Exception as e:
        logger.error(f"❌ Failed to create SKU Features table: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Create Demand Features
    logger.info(f"📈 Creating demand features from WEEKLY_UNITS...")
    demand_df = create_demand_features(sku_df)
    logger.info(f"✅ Created demand features for {len(demand_df)} SKUs")

    # Create Demand Features table
    logger.info(f"🔧 Creating Demand Features table: {DEMAND_FEATURES_PATH}")
    try:
        demand_features_spark = spark.createDataFrame(demand_df)

        # Drop existing table
        spark.sql(f"DROP TABLE IF EXISTS {DEMAND_FEATURES_PATH}")

        # Create feature table
        fe.create_table(
            name=DEMAND_FEATURES_PATH,
            primary_keys=["SKU_ID"],
            df=demand_features_spark,
            description="Demand forecast features for range optimization including weekly units, volatility, and forecasts"
        )
        logger.info(f"✅ Created Demand Features table with {len(demand_df)} SKUs")
    except Exception as e:
        logger.error(f"❌ Failed to create Demand Features table: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Verify tables
    logger.info("🔍 Verifying Feature Store tables...")
    try:
        sku_count = spark.table(PRODUCT_FEATURES_PATH).count()
        demand_count = spark.table(DEMAND_FEATURES_PATH).count()

        logger.info("=" * 80)
        logger.info("✅ Feature Store Tables Created Successfully!")
        logger.info("=" * 80)
        logger.info(f"📦 SKU Features: {PRODUCT_FEATURES_PATH} ({sku_count} rows)")
        logger.info(f"📊 Demand Features: {DEMAND_FEATURES_PATH} ({demand_count} rows)")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Train model: Run notebooks/01_train_stock_optimizer.py")
        logger.info("  2. Deploy endpoint: Run notebooks/02_deploy_serving_endpoint.py")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"❌ Failed to verify tables: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
