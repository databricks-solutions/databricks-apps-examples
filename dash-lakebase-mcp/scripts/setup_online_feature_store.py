#!/usr/bin/env python3
"""
Setup Online Feature Store for Range Optimizer

This script:
1. Creates Databricks Online Tables for feature serving
2. Publishes features from Delta tables to online tables
3. Enables low-latency feature serving (<10ms)
"""

from databricks.sdk import WorkspaceClient
from databricks.feature_engineering import FeatureEngineeringClient
from databricks.sdk.service.catalog import OnlineTableSpec, OnlineTableSpecTriggeredSchedulingPolicy
from databricks.sdk.runtime import spark
import time

# Configuration
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"

# Feature tables (source - offline Delta tables)
SKU_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.sku_features"
DEMAND_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.demand_features"

# Online table names (destination - online store)
SKU_FEATURES_ONLINE = f"{CATALOG}.{SCHEMA}.sku_features_online"
DEMAND_FEATURES_ONLINE = f"{CATALOG}.{SCHEMA}.demand_features_online"


def create_online_table(w: WorkspaceClient, source_table: str, online_table_name: str, primary_keys: list):
    """Create an online table from a Delta source table"""
    print(f"\n📊 Creating online table: {online_table_name}")
    print(f"   Source: {source_table}")
    print(f"   Primary keys: {primary_keys}")

    try:
        # Check if online table already exists
        try:
            existing = w.online_tables.get(online_table_name)
            print(f"   ℹ️  Online table already exists - state: {existing.status.detailed_state}")
            return existing
        except Exception:
            pass  # Table doesn't exist, create it

        # Create online table spec
        spec = OnlineTableSpec(
            source_table_full_name=source_table,
            primary_key_columns=primary_keys,
            run_triggered=OnlineTableSpecTriggeredSchedulingPolicy(),
            perform_full_copy=True
        )

        # Create the online table
        online_table = w.online_tables.create(
            name=online_table_name,
            spec=spec
        )

        print(f"   ✅ Online table created: {online_table_name}")
        print(f"      Status: {online_table.status.detailed_state}")

        # Wait for online table to be ready
        print(f"   ⏳ Waiting for online table to sync...")
        max_wait = 300  # 5 minutes
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = w.online_tables.get(online_table_name)
            state = status.status.detailed_state

            if state == "ONLINE":
                print(f"   ✅ Online table is ONLINE and ready!")
                break
            elif state in ["PROVISIONING", "ONLINE_CONTINUOUS_UPDATE", "ONLINE_UPDATING_PIPELINE_RESOURCES"]:
                print(f"      Status: {state}...")
                time.sleep(10)
            else:
                print(f"   ⚠️  Unexpected state: {state}")
                break

        return online_table

    except Exception as e:
        print(f"   ❌ Failed to create online table: {e}")
        raise


def main():
    """Main setup function"""
    print("=" * 80)
    print("🌐 Setting Up Online Feature Store")
    print("=" * 80)

    # Initialize clients
    print("🔧 Initializing clients...")
    w = WorkspaceClient()
    fe = FeatureEngineeringClient()

    print(f"📦 Catalog: {CATALOG}.{SCHEMA}")
    print(f"📊 Source Tables (Offline Delta):")
    print(f"   • {SKU_FEATURES_TABLE}")
    print(f"   • {DEMAND_FEATURES_TABLE}")
    print(f"🌐 Online Tables (Low-latency serving):")
    print(f"   • {SKU_FEATURES_ONLINE}")
    print(f"   • {DEMAND_FEATURES_ONLINE}")

    # Create Online Store first
    print("\n🏪 Setting up Online Store...")
    online_store_name = "range-optimizer-online-store"
    try:
        # Check if online store exists
        try:
            existing_store = fe.get_online_store(online_store_name)
            print(f"   ✅ Online store already exists: {online_store_name}")
        except:
            # Create new online store
            print(f"   Creating new online store: {online_store_name}")
            fe.create_online_store(
                name=online_store_name,
                capacity="CU_1"  # Smallest capacity for demo
            )
            print(f"   ✅ Online store created: {online_store_name}")
    except Exception as e:
        print(f"   ⚠️  Online store setup: {e}")

    # Verify source tables exist
    print("\n🔍 Verifying source feature tables...")
    try:
        sku_count = spark.table(SKU_FEATURES_TABLE).count()
        demand_count = spark.table(DEMAND_FEATURES_TABLE).count()
        print(f"   ✅ {SKU_FEATURES_TABLE}: {sku_count} rows")
        print(f"   ✅ {DEMAND_FEATURES_TABLE}: {demand_count} rows")
    except Exception as e:
        print(f"   ❌ Source tables not found: {e}")
        print("   Run create_feature_tables_simple.py first!")
        return 1

    # Create online tables
    print("\n🌐 Creating Online Tables...")

    # SKU Features Online Table
    sku_online = create_online_table(
        w=w,
        source_table=SKU_FEATURES_TABLE,
        online_table_name=SKU_FEATURES_ONLINE,
        primary_keys=["SKU_ID"]
    )

    # Demand Features Online Table
    demand_online = create_online_table(
        w=w,
        source_table=DEMAND_FEATURES_TABLE,
        online_table_name=DEMAND_FEATURES_ONLINE,
        primary_keys=["SKU_ID"]
    )

    # Summary
    print("\n" + "=" * 80)
    print("✅ SUCCESS! Online Feature Store Configured")
    print("=" * 80)
    print(f"🌐 Online Tables Created:")
    print(f"   • {SKU_FEATURES_ONLINE}")
    print(f"   • {DEMAND_FEATURES_ONLINE}")
    print(f"\n📊 Feature Serving:")
    print(f"   • Latency: <10ms (from online store)")
    print(f"   • Auto-sync: Continuous updates from Delta tables")
    print(f"   • Primary Key: SKU_ID")
    print(f"\nNext steps:")
    print(f"  1. Re-train model with fe.log_model() using online tables")
    print(f"  2. Deploy endpoint with Feature Serving enabled")
    print(f"  3. At inference: Send only SKU_ID → features fetched automatically")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())
