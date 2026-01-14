#!/usr/bin/env python3
"""
Simple script to create Feature Store tables in Unity Catalog.

This script reads SKU data from Lakebase and creates Feature Store tables.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from databricks.sdk import WorkspaceClient
from databricks.feature_engineering import FeatureEngineeringClient
import psycopg
import uuid

# Configuration
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"
PRODUCT_FEATURES_TABLE = "sku_features"
DEMAND_FEATURES_TABLE = "demand_features"

PRODUCT_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{PRODUCT_FEATURES_TABLE}"
DEMAND_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{DEMAND_FEATURES_TABLE}"

# Database config
LAKEBASE_SCHEMA = "range_optimizer"
LAKEBASE_DATABASE = "databricks_postgres"


class RotatingTokenConnection(psycopg.Connection):
    """psycopg3 Connection with OAuth token rotation"""

    @classmethod
    def connect(cls, conninfo: str = "", **kwargs):
        w = WorkspaceClient()
        instance_name = kwargs.pop("_instance_name")

        # Generate fresh OAuth token
        token = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[instance_name]
        ).token

        kwargs["password"] = token
        kwargs.setdefault("sslmode", "require")
        return super().connect(conninfo, **kwargs)


def get_lakebase_data():
    """Read SKU data from Lakebase PostgreSQL"""
    print("📡 Connecting to Lakebase PostgreSQL...")

    w = WorkspaceClient()
    user = w.current_user.me().user_name

    # Get Lakebase instance (try common names)
    instance_names = ["daveok", "range-opt", "range_opt"]
    host = None
    instance_name = None

    for name in instance_names:
        try:
            instance = w.database.get_database_instance(name=name)
            host = instance.read_write_dns
            instance_name = name
            print(f"   Instance: {instance_name}")
            print(f"   Host: {host}")
            print(f"   User: {user}")
            break
        except Exception as e:
            continue

    if not host:
        print(f"⚠️  Could not find Lakebase instance (tried: {instance_names})")
        return None

    try:
        conn = RotatingTokenConnection.connect(
            host=host,
            port=5432,
            dbname=LAKEBASE_DATABASE,
            user=user,
            _instance_name=instance_name
        )

        query = f'SELECT * FROM {LAKEBASE_SCHEMA}.dim_sku'
        df = pd.read_sql(query, conn)
        conn.close()

        print(f"✅ Loaded {len(df)} SKUs from Lakebase")
        return df

    except Exception as e:
        print(f"⚠️  Failed to read from Lakebase: {e}")
        return None


def create_demand_features(sku_df: pd.DataFrame) -> pd.DataFrame:
    """Create demand features from SKU data"""
    np.random.seed(42)

    category_variance = {
        'Beer & Seltzer': 0.25,
        'Hot Sauce': 0.20,
        'Ice Cream': 0.35,
    }

    demand_data = []
    for _, row in sku_df.iterrows():
        weekly_units = row.get('WEEKLY_UNITS', row.get('weekly_units', 50))
        if pd.isna(weekly_units):
            weekly_units = 50
        weekly_units = float(weekly_units)

        category = row.get('CATEGORY', row.get('category', 'Unknown'))
        variance_mult = category_variance.get(category, 0.25)
        demand_std = weekly_units * variance_mult
        forecast_4w = weekly_units * 4

        demand_data.append({
            'SKU_ID': row.get('SKU_ID', row.get('sku_id')),
            'WEEKLY_UNITS': round(weekly_units, 2),
            'DEMAND_STD': round(demand_std, 2),
            'FORECAST_4W': round(forecast_4w, 2),
            'FORECAST_DATE': datetime.now().date().isoformat(),
            'LAST_UPDATED': datetime.now().isoformat()
        })

    return pd.DataFrame(demand_data)


def get_fallback_data():
    """Get fallback sample data if Lakebase is unavailable"""
    print("📦 Using fallback sample data...")
    return pd.DataFrame([
        {"SKU_ID": "SKU3001", "SKU_NAME": "Stone & Wood Pacific Ale 6pk", "BRAND": "Stone & Wood",
         "CATEGORY": "Beer & Seltzer", "SEGMENT": "Craft Beer", "PACK_SIZE": "6x330ml",
         "PACK_WIDTH_MM": 180, "UNIT_PRICE": 24.00, "UNIT_COST": 14.40, "GROSS_MARGIN_PCT": 40,
         "WEEKLY_UNITS": 85, "CURRENT_FACINGS": 3, "IS_PRIVATE_LABEL": False,
         "IS_MUST_STOCK": True, "STATUS": "active"},
        {"SKU_ID": "SKU3002", "SKU_NAME": "Stone & Wood Green Coast Lager 6pk", "BRAND": "Stone & Wood",
         "CATEGORY": "Beer & Seltzer", "SEGMENT": "Craft Beer", "PACK_SIZE": "6x330ml",
         "PACK_WIDTH_MM": 180, "UNIT_PRICE": 23.00, "UNIT_COST": 13.80, "GROSS_MARGIN_PCT": 40,
         "WEEKLY_UNITS": 65, "CURRENT_FACINGS": 2, "IS_PRIVATE_LABEL": False,
         "IS_MUST_STOCK": False, "STATUS": "active"},
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


def main():
    """Main execution"""
    print("=" * 80)
    print("🎯 Creating Feature Store Tables for Range Optimization")
    print("=" * 80)

    # Initialize clients
    print("🔧 Initializing Databricks clients...")
    w = WorkspaceClient()
    fe = FeatureEngineeringClient()

    # Get Spark session
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        print("✅ Spark session ready")
    except Exception as e:
        print(f"❌ Failed to get Spark session: {e}")
        return 1

    # Create catalog and schema
    print(f"📁 Setting up catalog: {CATALOG}.{SCHEMA}")
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
        print(f"✅ Catalog and schema ready")
    except Exception as e:
        print(f"⚠️  Warning during schema setup: {e}")

    # Load SKU data
    sku_df = get_lakebase_data()
    if sku_df is None or len(sku_df) == 0:
        sku_df = get_fallback_data()

    # Normalize column names to uppercase
    sku_df.columns = [col.upper() for col in sku_df.columns]

    if 'CREATED_AT' not in sku_df.columns:
        sku_df['CREATED_AT'] = datetime.now().isoformat()

    print(f"📊 Working with {len(sku_df)} SKUs")

    # Create SKU Features Table
    print(f"🔧 Creating SKU Features: {PRODUCT_FEATURES_PATH}")
    try:
        sku_spark = spark.createDataFrame(sku_df)
        spark.sql(f"DROP TABLE IF EXISTS {PRODUCT_FEATURES_PATH}")

        fe.create_table(
            name=PRODUCT_FEATURES_PATH,
            primary_keys=["SKU_ID"],
            df=sku_spark,
            description="SKU features for range optimization"
        )
        print(f"✅ Created SKU Features table")
    except Exception as e:
        print(f"❌ Failed to create SKU Features: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Create Demand Features
    print(f"📈 Creating demand features...")
    demand_df = create_demand_features(sku_df)
    print(f"✅ Created demand features for {len(demand_df)} SKUs")

    # Create Demand Features Table
    print(f"🔧 Creating Demand Features: {DEMAND_FEATURES_PATH}")
    try:
        demand_spark = spark.createDataFrame(demand_df)
        spark.sql(f"DROP TABLE IF EXISTS {DEMAND_FEATURES_PATH}")

        fe.create_table(
            name=DEMAND_FEATURES_PATH,
            primary_keys=["SKU_ID"],
            df=demand_spark,
            description="Demand forecast features for range optimization"
        )
        print(f"✅ Created Demand Features table")
    except Exception as e:
        print(f"❌ Failed to create Demand Features: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Verify
    print("🔍 Verifying tables...")
    try:
        sku_count = spark.table(PRODUCT_FEATURES_PATH).count()
        demand_count = spark.table(DEMAND_FEATURES_PATH).count()

        print("=" * 80)
        print("✅ SUCCESS! Feature Store Tables Created")
        print("=" * 80)
        print(f"📦 {PRODUCT_FEATURES_PATH}: {sku_count} rows")
        print(f"📊 {DEMAND_FEATURES_PATH}: {demand_count} rows")
        print("")
        print("Next steps:")
        print("  1. Train model: notebooks/01_train_stock_optimizer.py")
        print("  2. Deploy endpoint: notebooks/02_deploy_serving_endpoint.py")
        print("=" * 80)
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
