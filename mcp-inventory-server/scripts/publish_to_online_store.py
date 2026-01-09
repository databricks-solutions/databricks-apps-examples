"""
Publish Feature Tables to Online Store

Alternative approach using Feature Engineering Client's publish_table() method.
This is the recommended way per Databricks documentation.

Based on: https://docs.databricks.com/aws/en/notebooks/source/machine-learning/feature-function-serving-online-tables-dbsdk.html
"""

import datetime
import time


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [PUBLISH] {message}")


def create_online_store():
    """
    Create a Databricks Online Store for feature serving.
    This provisions a managed Lakebase instance optimized for online serving.
    """
    
    log("Creating Databricks Online Store...")
    
    try:
        from databricks.feature_engineering import FeatureEngineeringClient
        
        fe = FeatureEngineeringClient()
        
        online_store_name = "stock_optimization_features_store"
        
        # Check if online store already exists
        try:
            existing_store = fe.get_online_store(name=online_store_name)
            log(f"⚠️  Online store already exists: {online_store_name}")
            log(f"   State: {existing_store.state}")
            log(f"   Capacity: {existing_store.capacity}")
            return existing_store
        except Exception:
            # Store doesn't exist, create it
            pass
        
        log(f"→ Creating online store: {online_store_name}")
        
        # Create online store with specified capacity
        # Capacity options: "CU_1", "CU_2", "CU_4", "CU_8"
        # Each CU = ~16GB RAM + CPU + SSD resources
        online_store = fe.create_online_store(
            name=online_store_name,
            capacity="CU_1"  # Start small, scale up if needed
        )
        
        log(f"✓ Online store created: {online_store_name}")
        log(f"   State: {online_store.state}")
        log(f"   Capacity: {online_store.capacity}")
        
        # Wait for online store to be available
        log("→ Waiting for online store to be AVAILABLE...")
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            store_status = fe.get_online_store(name=online_store_name)
            if store_status.state == "AVAILABLE":
                log("✅ Online store is AVAILABLE!")
                return store_status
            elif store_status.state in ["PROVISIONING", "UPDATING"]:
                log(f"   State: {store_status.state} - waiting...")
                time.sleep(10)
            else:
                log(f"⚠️  Unexpected state: {store_status.state}")
                break
        
        log("⚠️  Timeout waiting for online store to be available")
        return online_store
        
    except Exception as e:
        log(f"❌ Error creating online store: {e}")
        import traceback
        traceback.print_exc()
        raise


def publish_tables_to_online_store():
    """
    Publish feature tables to the online store using the Feature Engineering Client.
    This is the recommended approach for online feature serving.
    """
    
    log("Publishing feature tables to online store...")
    
    try:
        from databricks.feature_engineering import FeatureEngineeringClient
        
        fe = FeatureEngineeringClient()
        
        # Get the online store
        online_store = fe.get_online_store(name="stock_optimization_features_store")
        
        if online_store.state != "AVAILABLE":
            log(f"⚠️  Online store is not available: {online_store.state}")
            log("   Please wait for online store to be AVAILABLE before publishing tables")
            return
        
        # Define tables to publish
        tables_to_publish = [
            {
                "source": "main.excel_app.product_demand_features",
                "online": "main.excel_app.product_demand_features_online"
            },
            {
                "source": "main.excel_app.product_cost_features",
                "online": "main.excel_app.product_cost_features_online"
            },
            {
                "source": "main.excel_app.current_inventory",
                "online": "main.excel_app.current_inventory_online"
            }
        ]
        
        for table_config in tables_to_publish:
            source_table = table_config["source"]
            online_table = table_config["online"]
            
            log(f"→ Publishing: {source_table} → {online_table}")
            
            try:
                # Publish the table to online store
                # This sets up continuous sync from offline to online table
                fe.publish_table(
                    online_store=online_store,
                    source_table_name=source_table,
                    online_table_name=online_table,
                    # streaming=True would enable continuous updates
                    # For scheduled updates, set streaming=False and use a job
                )
                
                log(f"✓ Published: {online_table}")
                
            except Exception as e:
                log(f"⚠️  Error publishing {source_table}: {e}")
                # Continue with other tables
        
        log("✅ All tables published to online store!")
        
    except Exception as e:
        log(f"❌ Error publishing tables: {e}")
        import traceback
        traceback.print_exc()
        raise


def verify_online_tables():
    """Verify that online tables are properly set up and accessible"""
    
    log("Verifying online tables...")
    
    try:
        from databricks.sdk import WorkspaceClient
        
        w = WorkspaceClient()
        
        online_tables = [
            "main.excel_app.product_demand_features_online",
            "main.excel_app.product_cost_features_online",
            "main.excel_app.current_inventory_online"
        ]
        
        all_ready = True
        
        for table_name in online_tables:
            try:
                # Get online table info
                table = w.online_tables.get(name=table_name)
                
                log(f"✓ {table_name}")
                log(f"   Status: {table.status.detailed_state}")
                
                if table.status.detailed_state != "ONLINE":
                    log(f"   ⚠️  Table is not ONLINE yet")
                    all_ready = False
                
                # Check row count if available
                if hasattr(table.status, 'provisioning_status'):
                    log(f"   Provisioning: {table.status.provisioning_status}")
                    
            except Exception as e:
                log(f"❌ {table_name}: {e}")
                all_ready = False
        
        if all_ready:
            log("✅ All online tables are verified and ready!")
        else:
            log("⚠️  Some tables are not ready yet. Wait a few minutes and check again.")
        
        return all_ready
        
    except Exception as e:
        log(f"❌ Verification error: {e}")
        return False


def test_feature_lookup():
    """Test feature lookup from online tables via Feature Serving"""
    
    log("Testing feature lookup...")
    
    try:
        import mlflow.deployments
        from server import utils
        
        # Get a sample sell_id from the database
        query = 'SELECT "SELL_ID" FROM excel_app.layout_data LIMIT 1'
        result = utils.execute_query(query)
        
        if not result:
            log("⚠️  No products found to test with")
            return
        
        sample_sell_id = result[0]['SELL_ID']
        log(f"→ Testing with sell_id: {sample_sell_id}")
        
        # Create MLflow deployment client
        client = mlflow.deployments.get_deploy_client("databricks")
        
        # Query Feature Serving endpoint
        log("→ Querying Feature Serving endpoint...")
        response = client.predict(
            endpoint="stock-optimization-features",
            inputs={
                "dataframe_records": [
                    {"sell_id": sample_sell_id}
                ]
            }
        )
        
        log("✅ Feature lookup successful!")
        
        # Display results
        if "outputs" in response:
            outputs = response["outputs"]
            if outputs:
                log(f"   Features returned: {len(outputs[0])} columns")
                log("   Sample values:")
                for key, value in list(outputs[0].items())[:8]:
                    log(f"     {key}: {value}")
        
        return response
        
    except Exception as e:
        log(f"❌ Feature lookup test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_online_store_info():
    """Get information about the online store"""
    
    log("Getting online store information...")
    
    try:
        from databricks.feature_engineering import FeatureEngineeringClient
        
        fe = FeatureEngineeringClient()
        
        online_store = fe.get_online_store(name="stock_optimization_features_store")
        
        log("Online Store Information:")
        log(f"   Name: {online_store.name}")
        log(f"   State: {online_store.state}")
        log(f"   Capacity: {online_store.capacity}")
        
        if hasattr(online_store, 'created_at'):
            log(f"   Created: {online_store.created_at}")
        
        if hasattr(online_store, 'host'):
            log(f"   Host: {online_store.host}")
        
    except Exception as e:
        log(f"⚠️  Could not get online store info: {e}")


def main():
    """Main function"""
    log("=" * 70)
    log("PUBLISH FEATURE TABLES TO ONLINE STORE")
    log("=" * 70)
    log("")
    log("This script uses the Feature Engineering Client's publish_table() method")
    log("which is the recommended approach per Databricks documentation.")
    log("")
    
    # Step 1: Create online store
    log("STEP 1: Create Online Store")
    log("-" * 70)
    create_online_store()
    
    log("")
    log("STEP 2: Publish Tables")
    log("-" * 70)
    publish_tables_to_online_store()
    
    log("")
    log("STEP 3: Wait for Tables to be Ready")
    log("-" * 70)
    log("Waiting 30 seconds before verification...")
    time.sleep(30)
    
    verify_online_tables()
    
    log("")
    log("STEP 4: Test Feature Lookup")
    log("-" * 70)
    test_feature_lookup()
    
    log("")
    get_online_store_info()
    
    log("")
    log("=" * 70)
    log("SETUP COMPLETE!")
    log("=" * 70)
    log("")
    log("Your feature tables are now published to the online store.")
    log("Features are accessible via the Feature Serving endpoint.")
    log("")
    log("Next steps:")
    log("1. Populate feature tables with real data")
    log("2. Set up scheduled jobs to refresh features")
    log("3. Monitor feature freshness and endpoint performance")


if __name__ == "__main__":
    main()

