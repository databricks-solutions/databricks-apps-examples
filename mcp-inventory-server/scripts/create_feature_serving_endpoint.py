"""
Create Feature Serving Endpoint

This script creates a Feature Serving endpoint for the stock optimization
FeatureSpec, enabling low-latency feature retrieval.
"""

import datetime
import time


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [ENDPOINT] {message}")


def create_feature_serving_endpoint():
    """Create the Feature Serving endpoint"""
    
    log("Creating Feature Serving endpoint...")
    
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
        
        workspace = WorkspaceClient()
        
        endpoint_name = "stock-optimization-features"
        
        # Check if endpoint already exists
        try:
            existing = workspace.serving_endpoints.get(name=endpoint_name)
            log(f"⚠️  Endpoint '{endpoint_name}' already exists with state: {existing.state.ready}")
            log("   To recreate, delete the endpoint first:")
            log(f"   databricks serving-endpoints delete {endpoint_name}")
            return
        except Exception:
            # Endpoint doesn't exist, we can create it
            pass
        
        log(f"→ Creating endpoint: {endpoint_name}")
        
        # Create endpoint for the feature spec
        endpoint = workspace.serving_endpoints.create(
            name=endpoint_name,
            config=EndpointCoreConfigInput(
                served_entities=[
                    ServedEntityInput(
                        entity_name="main.excel_app.stock_optimization_features",
                        scale_to_zero_enabled=True,
                        workload_size="Small"
                    )
                ]
            )
        )
        
        log("✓ Endpoint creation initiated")
        log(f"   Name: {endpoint_name}")
        log(f"   State: {endpoint.state.config_update}")
        
        # Wait for endpoint to be ready
        log("→ Waiting for endpoint to be ready (this may take a few minutes)...")
        
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                status = workspace.serving_endpoints.get(name=endpoint_name)
                
                if status.state.ready == "READY":
                    log("✅ Endpoint is READY!")
                    log(f"   URL: {status.url}")
                    return status
                elif status.state.ready in ["NOT_READY", "UPDATING"]:
                    log(f"   Status: {status.state.ready} - waiting...")
                    time.sleep(10)
                else:
                    log(f"⚠️  Unexpected state: {status.state.ready}")
                    break
                    
            except Exception as e:
                log(f"⚠️  Error checking status: {e}")
                time.sleep(10)
        
        log("⚠️  Endpoint creation timed out or failed")
        log("   Check status with: databricks serving-endpoints get stock-optimization-features")
        
    except Exception as e:
        log(f"❌ Error creating endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_endpoint():
    """Test the Feature Serving endpoint with sample data"""
    
    log("Testing Feature Serving endpoint...")
    
    try:
        import mlflow.deployments
        from server import utils
        
        # Get a sample sell_id
        query = 'SELECT "SELL_ID" FROM excel_app.layout_data LIMIT 2'
        result = utils.execute_query(query)
        
        if not result:
            log("⚠️  No products found to test with")
            return
        
        sell_ids = [row['SELL_ID'] for row in result]
        log(f"→ Testing with sell_ids: {sell_ids}")
        
        # Create client
        client = mlflow.deployments.get_deploy_client("databricks")
        
        # Query the endpoint
        log("→ Querying Feature Serving endpoint...")
        response = client.predict(
            endpoint="stock-optimization-features",
            inputs={
                "dataframe_records": [
                    {"sell_id": sell_id} for sell_id in sell_ids
                ]
            }
        )
        
        log("✅ Feature Serving endpoint test successful!")
        log(f"   Response keys: {list(response.keys())}")
        
        if 'outputs' in response:
            outputs = response['outputs']
            log(f"   Number of records: {len(outputs)}")
            if outputs:
                log(f"   Feature columns: {list(outputs[0].keys())}")
                log(f"   Sample values:")
                for key, value in list(outputs[0].items())[:5]:
                    log(f"     {key}: {value}")
        
        return response
        
    except Exception as e:
        log(f"⚠️  Endpoint test failed: {e}")
        import traceback
        traceback.print_exc()


def get_endpoint_info():
    """Get information about the endpoint"""
    
    log("Getting endpoint information...")
    
    try:
        from databricks.sdk import WorkspaceClient
        
        workspace = WorkspaceClient()
        endpoint = workspace.serving_endpoints.get(name="stock-optimization-features")
        
        log("Endpoint Information:")
        log(f"   Name: {endpoint.name}")
        log(f"   State: {endpoint.state.ready}")
        log(f"   URL: {endpoint.url}")
        log(f"   Creator: {endpoint.creator}")
        log(f"   Created: {endpoint.creation_timestamp}")
        
        if endpoint.config and endpoint.config.served_entities:
            for entity in endpoint.config.served_entities:
                log(f"   Entity: {entity.entity_name}")
                log(f"   Workload Size: {entity.workload_size}")
                log(f"   Scale to Zero: {entity.scale_to_zero_enabled}")
        
    except Exception as e:
        log(f"⚠️  Could not get endpoint info: {e}")


def main():
    """Main function"""
    log("=" * 70)
    log("FEATURE SERVING ENDPOINT CREATION")
    log("=" * 70)
    
    create_feature_serving_endpoint()
    
    log("")
    log("Waiting 5 seconds before testing...")
    time.sleep(5)
    
    test_endpoint()
    get_endpoint_info()
    
    log("=" * 70)
    log("FEATURE SERVING ENDPOINT SETUP COMPLETE!")
    log("=" * 70)
    log("")
    log("The Feature Serving endpoint is ready to use!")
    log("You can now update the MCP server to use this endpoint.")
    log("")
    log("Endpoint URL pattern:")
    log("  https://<workspace>/serving-endpoints/stock-optimization-features/invocations")


if __name__ == "__main__":
    main()

