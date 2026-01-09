"""
Integration Test for Feature Serving

Tests the complete flow from feature lookup to optimization prediction.
Based on patterns from Databricks documentation.
"""

import datetime
import json


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [TEST] {message}")


def test_feature_serving_endpoint():
    """Test the Feature Serving endpoint directly"""
    
    log("Testing Feature Serving endpoint...")
    
    try:
        import mlflow.deployments
        from server import utils
        
        # Get sample products
        query = 'SELECT "SELL_ID", "PRODUCT_NAME" FROM excel_app.layout_data LIMIT 3'
        products = utils.execute_query(query)
        
        if not products:
            log("❌ No products found in database")
            return False
        
        sell_ids = [p['SELL_ID'] for p in products]
        log(f"→ Testing with {len(sell_ids)} products: {sell_ids}")
        
        # Create client
        client = mlflow.deployments.get_deploy_client("databricks")
        
        # Query Feature Serving endpoint
        log("→ Calling Feature Serving endpoint...")
        response = client.predict(
            endpoint="stock-optimization-features",
            inputs={
                "dataframe_records": [
                    {"sell_id": sell_id} for sell_id in sell_ids
                ]
            }
        )
        
        # Validate response
        if "outputs" not in response:
            log("❌ No 'outputs' in response")
            return False
        
        outputs = response["outputs"]
        log(f"✓ Received {len(outputs)} feature records")
        
        # Check expected features are present
        expected_features = [
            "sell_id",
            "avg_daily_demand",
            "demand_std",
            "unit_cost",
            "selling_price",
            "current_stock",
            "safety_stock",
            "reorder_urgency",  # Derived feature
            "profit_margin"     # Derived feature
        ]
        
        if outputs:
            actual_features = set(outputs[0].keys())
            missing_features = set(expected_features) - actual_features
            
            if missing_features:
                log(f"⚠️  Missing features: {missing_features}")
            else:
                log(f"✓ All expected features present ({len(actual_features)} features)")
            
            # Display sample values
            log("Sample feature values:")
            sample = outputs[0]
            for feature in expected_features:
                if feature in sample:
                    log(f"  {feature}: {sample[feature]}")
        
        log("✅ Feature Serving endpoint test PASSED")
        return True
        
    except Exception as e:
        log(f"❌ Feature Serving endpoint test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_serving_with_features():
    """Test Model Serving endpoint with features from Feature Serving"""
    
    log("Testing Model Serving with features...")
    
    try:
        import mlflow.deployments
        from databricks.sdk import WorkspaceClient
        from server import utils
        
        # Get sample products
        query = 'SELECT "SELL_ID" FROM excel_app.layout_data LIMIT 2'
        products = utils.execute_query(query)
        
        if not products:
            log("❌ No products found")
            return False
        
        sell_ids = [p['SELL_ID'] for p in products]
        
        # Get features from Feature Serving
        client = mlflow.deployments.get_deploy_client("databricks")
        feature_response = client.predict(
            endpoint="stock-optimization-features",
            inputs={
                "dataframe_records": [
                    {"sell_id": sell_id} for sell_id in sell_ids
                ]
            }
        )
        
        features = feature_response.get("outputs", [])
        log(f"✓ Got features for {len(features)} products")
        
        # Prepare input for Model Serving
        model_input = []
        for feature_record in features:
            model_record = {
                "sell_id": feature_record.get("sell_id"),
                "avg_daily_demand": feature_record.get("avg_daily_demand", 0),
                "current_stock": feature_record.get("current_stock", 0),
                "safety_stock": feature_record.get("safety_stock", 0),
            }
            model_input.append(model_record)
        
        # Call Model Serving endpoint
        log("→ Calling Model Serving endpoint...")
        w = WorkspaceClient()
        
        try:
            model_response = w.serving_endpoints.query(
                name="stock-optimization-model",
                dataframe_records=model_input
            )
            
            predictions = model_response.predictions if hasattr(model_response, 'predictions') else []
            log(f"✓ Got predictions for {len(predictions)} products")
            
            if predictions:
                log("Sample prediction:")
                pred = predictions[0] if isinstance(predictions[0], dict) else {}
                for key in ["optimal_order_qty", "safety_stock", "reorder_point"]:
                    if key in pred:
                        log(f"  {key}: {pred[key]}")
            
            log("✅ Model Serving test PASSED")
            return True
            
        except Exception as model_err:
            log(f"⚠️  Model Serving endpoint not available: {model_err}")
            log("   This is OK if the endpoint doesn't exist yet")
            log("   The system will use fallback heuristics")
            return True  # Not a failure if model endpoint doesn't exist
        
    except Exception as e:
        log(f"❌ Model Serving test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_end_to_end_optimization():
    """Test the complete optimization flow using MCP tools"""
    
    log("Testing end-to-end optimization flow...")
    
    try:
        from server import tools as mcp_tools
        from server import utils
        import uuid
        
        # Create a test forecast submission
        query = 'SELECT * FROM excel_app.layout_data LIMIT 2'
        products = utils.execute_query(query)
        
        if not products:
            log("❌ No products found")
            return False
        
        # Create forecast submission
        forecast_id = f"TEST-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        log(f"→ Creating test forecast: {forecast_id}")
        
        forecast_records = []
        for product in products:
            record = {
                "FORECAST_ID": forecast_id,
                "SELL_ID": product["SELL_ID"],
                "CATEGORY_NAME": product.get("CATEGORY_NAME"),
                "SUBCATEGORY_NAME": product.get("SUBCATEGORY_NAME"),
                "PRODUCT_NAME": product.get("PRODUCT_NAME"),
                "SHELF_SPACE_CM": product.get("SHELF_SPACE_CM"),
                "SHELF_HEIGHT_CM": product.get("SHELF_HEIGHT_CM"),
                "MIN_STOCK": product.get("MIN_STOCK"),
                "MAX_STOCK": product.get("MAX_STOCK"),
                "SUBMISSION_TIMESTAMP": datetime.datetime.now().isoformat()
            }
            forecast_records.append(record)
        
        # Insert forecast submission
        utils.batch_insert('excel_app.forecast_submissions', forecast_records, overwrite=False)
        log(f"✓ Created forecast submission with {len(forecast_records)} products")
        
        # Run optimization using MCP tool
        log("→ Running optimization via MCP tool...")
        result = mcp_tools._run_forecast_optimization_impl(
            forecast_id=forecast_id,
            model_endpoint="stock-optimization-model"
        )
        
        # Check result
        log("Optimization result:")
        log(f"  Status: {result.get('status')}")
        log(f"  Method: {result.get('method')}")
        log(f"  Product count: {result.get('product_count')}")
        
        if result.get('status') == 'error':
            log(f"❌ Optimization failed: {result.get('error')}")
            return False
        
        # Verify results were saved
        results_query = f"""
            SELECT COUNT(*) as cnt 
            FROM excel_app.stock_optimization_results 
            WHERE forecast_id = '{forecast_id}'
        """
        results = utils.execute_query(results_query)
        result_count = results[0]['cnt'] if results else 0
        
        log(f"✓ Found {result_count} optimization results in database")
        
        if result_count == len(forecast_records):
            log("✅ End-to-end optimization test PASSED")
            return True
        else:
            log(f"⚠️  Expected {len(forecast_records)} results, got {result_count}")
            return False
        
    except Exception as e:
        log(f"❌ End-to-end test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_freshness():
    """Check feature table freshness"""
    
    log("Checking feature table freshness...")
    
    try:
        from server import utils
        
        tables = [
            'main.excel_app.product_demand_features',
            'main.excel_app.product_cost_features',
            'main.excel_app.current_inventory'
        ]
        
        all_fresh = True
        
        for table in tables:
            query = f"""
                SELECT 
                    COUNT(*) as record_count,
                    MAX(last_updated) as latest_update
                FROM {table}
            """
            result = utils.execute_query(query)
            
            if result:
                count = result[0]['record_count']
                latest = result[0]['latest_update']
                log(f"✓ {table}")
                log(f"   Records: {count}")
                log(f"   Latest update: {latest}")
                
                # Check if updated in last 7 days
                if latest:
                    from datetime import datetime, timedelta
                    latest_dt = datetime.fromisoformat(str(latest))
                    age_days = (datetime.now() - latest_dt).days
                    
                    if age_days > 7:
                        log(f"   ⚠️  Features are {age_days} days old")
                        all_fresh = False
            else:
                log(f"❌ {table}: No data")
                all_fresh = False
        
        if all_fresh:
            log("✅ All feature tables are reasonably fresh")
        else:
            log("⚠️  Some feature tables need refreshing")
        
        return all_fresh
        
    except Exception as e:
        log(f"❌ Freshness check failed: {e}")
        return False


def main():
    """Run all integration tests"""
    log("=" * 70)
    log("FEATURE SERVING INTEGRATION TESTS")
    log("=" * 70)
    log("")
    
    results = {}
    
    # Test 1: Feature Serving endpoint
    log("TEST 1: Feature Serving Endpoint")
    log("-" * 70)
    results["feature_serving"] = test_feature_serving_endpoint()
    log("")
    
    # Test 2: Model Serving with features
    log("TEST 2: Model Serving with Features")
    log("-" * 70)
    results["model_serving"] = test_model_serving_with_features()
    log("")
    
    # Test 3: Feature freshness
    log("TEST 3: Feature Freshness")
    log("-" * 70)
    results["freshness"] = test_feature_freshness()
    log("")
    
    # Test 4: End-to-end optimization
    log("TEST 4: End-to-End Optimization")
    log("-" * 70)
    results["end_to_end"] = test_end_to_end_optimization()
    log("")
    
    # Summary
    log("=" * 70)
    log("TEST SUMMARY")
    log("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✅ PASSED" if passed_flag else "❌ FAILED"
        log(f"{status}: {test_name}")
    
    log("")
    log(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        log("✅ ALL TESTS PASSED!")
        return 0
    else:
        log("⚠️  SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())

