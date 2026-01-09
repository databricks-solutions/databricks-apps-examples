"""
Setup Online Tables for Feature Serving

This script creates online tables that sync from offline feature tables,
providing low-latency feature lookups for real-time serving.

Based on: https://docs.databricks.com/aws/en/notebooks/source/machine-learning/feature-function-serving-online-tables-dbsdk.html
"""

import datetime
import time


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [ONLINE-TABLE] {message}")


def create_online_tables():
    """Create online tables for feature serving"""
    
    log("Creating online tables...")
    
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.catalog import (
            OnlineTableSpec,
            OnlineTableSpecTriggeredSchedulingPolicy
        )
        
        w = WorkspaceClient()
        
        # Define the feature tables to publish as online tables
        feature_tables = [
            {
                "name": "product_demand_features_online",
                "source_table": "main.excel_app.product_demand_features",
                "primary_key": "sell_id",
                "timeseries_key": None  # Latest values only
            },
            {
                "name": "product_cost_features_online",
                "source_table": "main.excel_app.product_cost_features",
                "primary_key": "sell_id",
                "timeseries_key": None
            },
            {
                "name": "current_inventory_online",
                "source_table": "main.excel_app.current_inventory",
                "primary_key": "sell_id",
                "timeseries_key": None
            }
        ]
        
        for table_config in feature_tables:
            online_table_name = f"main.excel_app.{table_config['name']}"
            
            log(f"→ Creating online table: {online_table_name}")
            
            try:
                # Check if online table already exists
                existing = w.online_tables.get(name=online_table_name)
                log(f"⚠️  Online table already exists: {online_table_name}")
                log(f"   Status: {existing.status.detailed_state}")
                continue
            except Exception:
                # Table doesn't exist, create it
                pass
            
            # Create online table spec
            spec = OnlineTableSpec(
                source_table_full_name=table_config["source_table"],
                primary_key_columns=[table_config["primary_key"]],
                timeseries_key=table_config["timeseries_key"],
                run_triggered=OnlineTableSpecTriggeredSchedulingPolicy.from_dict({
                    "triggered": {}  # Manual refresh
                }),
                perform_full_copy=True  # Initial full copy
            )
            
            # Create the online table
            online_table = w.online_tables.create(
                name=online_table_name,
                spec=spec
            )
            
            log(f"✓ Online table created: {online_table_name}")
            log(f"   Status: {online_table.status.detailed_state}")
        
        log("✅ All online tables created!")
        
    except Exception as e:
        log(f"❌ Error creating online tables: {e}")
        import traceback
        traceback.print_exc()
        raise


def wait_for_online_tables():
    """Wait for online tables to be ready"""
    
    log("Waiting for online tables to be ready...")
    
    try:
        from databricks.sdk import WorkspaceClient
        
        w = WorkspaceClient()
        
        online_tables = [
            "main.excel_app.product_demand_features_online",
            "main.excel_app.product_cost_features_online",
            "main.excel_app.current_inventory_online"
        ]
        
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            all_ready = True
            
            for table_name in online_tables:
                try:
                    table = w.online_tables.get(name=table_name)
                    status = table.status.detailed_state
                    
                    if status == "ONLINE":
                        log(f"✓ {table_name}: ONLINE")
                    elif status in ["PROVISIONING", "ONLINE_PIPELINE_RUNNING"]:
                        log(f"  {table_name}: {status} - waiting...")
                        all_ready = False
                    else:
                        log(f"⚠️  {table_name}: {status}")
                        all_ready = False
                        
                except Exception as e:
                    log(f"⚠️  {table_name}: Error - {e}")
                    all_ready = False
            
            if all_ready:
                log("✅ All online tables are ONLINE!")
                return True
            
            time.sleep(10)
        
        log("⚠️  Timeout waiting for online tables")
        return False
        
    except Exception as e:
        log(f"❌ Error checking online tables: {e}")
        return False


def verify_online_tables():
    """Verify online tables are working"""
    
    log("Verifying online tables...")
    
    try:
        from databricks.sdk import WorkspaceClient
        
        w = WorkspaceClient()
        
        online_tables = [
            "main.excel_app.product_demand_features_online",
            "main.excel_app.product_cost_features_online",
            "main.excel_app.current_inventory_online"
        ]
        
        for table_name in online_tables:
            try:
                table = w.online_tables.get(name=table_name)
                log(f"✓ {table_name}")
                log(f"   Status: {table.status.detailed_state}")
                log(f"   Source: {table.spec.source_table_full_name}")
                log(f"   Primary Key: {table.spec.primary_key_columns}")
                
            except Exception as e:
                log(f"❌ {table_name}: {e}")
        
        log("✓ Verification complete")
        
    except Exception as e:
        log(f"❌ Verification error: {e}")


def main():
    """Main function"""
    log("=" * 70)
    log("ONLINE TABLES SETUP")
    log("=" * 70)
    log("")
    log("This creates online tables for low-latency feature serving.")
    log("Online tables sync from offline Delta tables automatically.")
    log("")
    
    create_online_tables()
    
    log("")
    log("Waiting for tables to come online (this may take a few minutes)...")
    wait_for_online_tables()
    
    log("")
    verify_online_tables()
    
    log("=" * 70)
    log("ONLINE TABLES SETUP COMPLETE!")
    log("=" * 70)
    log("")
    log("Next steps:")
    log("1. Update FeatureSpec to use online tables")
    log("2. Create Feature Serving endpoint")


if __name__ == "__main__":
    main()

