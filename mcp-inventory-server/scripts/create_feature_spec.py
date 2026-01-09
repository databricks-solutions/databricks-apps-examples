"""
Create FeatureSpec for Stock Optimization

This script creates the FeatureSpec that defines which features to use
for stock optimization, including feature lookups and transformations.
"""

import datetime


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [FEATURE-SPEC] {message}")


def create_feature_spec():
    """Create the FeatureSpec for stock optimization"""
    
    log("Creating FeatureSpec...")
    
    try:
        from databricks.feature_engineering import (
            FeatureEngineeringClient,
            FeatureLookup,
            FeatureFunction,
        )
        
        fe = FeatureEngineeringClient()
        
        # Define the features for stock optimization
        # Use online tables for low-latency lookups
        features = [
            # Lookup demand forecasting features from online table
            FeatureLookup(
                table_name="main.excel_app.product_demand_features_online",
                lookup_key="sell_id",
                feature_names=[
                    "avg_daily_demand",
                    "demand_std",
                    "total_forecast_30d",
                    "seasonal_factor",
                    "trend_factor"
                ]
            ),
            
            # Lookup cost and pricing features from online table
            FeatureLookup(
                table_name="main.excel_app.product_cost_features_online",
                lookup_key="sell_id",
                feature_names=[
                    "unit_cost",
                    "selling_price",
                    "holding_cost_rate",
                    "ordering_cost"
                ]
            ),
            
            # Lookup current inventory state from online table
            FeatureLookup(
                table_name="main.excel_app.current_inventory_online",
                lookup_key="sell_id",
                feature_names=[
                    "current_stock",
                    "safety_stock"
                ]
            ),
            
            # Calculate derived features using UC functions
            FeatureFunction(
                udf_name="main.excel_app.calculate_reorder_urgency",
                output_name="reorder_urgency",
                input_bindings={
                    "current_stock": "current_stock",
                    "avg_daily_demand": "avg_daily_demand",
                    "safety_stock": "safety_stock"
                }
            ),
            
            FeatureFunction(
                udf_name="main.excel_app.calculate_lead_time_demand",
                output_name="lead_time_demand",
                input_bindings={
                    "avg_daily_demand": "avg_daily_demand",
                    "lead_time_days": 7.0  # Constant value
                }
            ),
            
            FeatureFunction(
                udf_name="main.excel_app.calculate_profit_margin",
                output_name="profit_margin",
                input_bindings={
                    "selling_price": "selling_price",
                    "unit_cost": "unit_cost"
                }
            ),
        ]
        
        log(f"→ Creating FeatureSpec with {len(features)} features...")
        
        # Create the FeatureSpec (stored as a UC function)
        feature_spec = fe.create_feature_spec(
            name="main.excel_app.stock_optimization_features",
            features=features,
            exclude_columns=None  # Include all features
        )
        
        log("✅ FeatureSpec created successfully!")
        log(f"   Name: main.excel_app.stock_optimization_features")
        log(f"   Features: {len(features)}")
        
        return feature_spec
        
    except Exception as e:
        log(f"❌ Error creating FeatureSpec: {e}")
        import traceback
        traceback.print_exc()
        raise


def verify_feature_spec():
    """Verify that the FeatureSpec was created"""
    
    log("Verifying FeatureSpec...")
    
    try:
        from databricks.feature_engineering import FeatureEngineeringClient
        
        fe = FeatureEngineeringClient()
        
        # Try to get the feature spec
        feature_spec = fe.get_feature_spec(name="main.excel_app.stock_optimization_features")
        
        log("✓ FeatureSpec retrieved successfully")
        log(f"   Name: {feature_spec.name}")
        
    except Exception as e:
        log(f"⚠️  Could not verify FeatureSpec: {e}")


def test_feature_spec():
    """Test the FeatureSpec with sample data"""
    
    log("Testing FeatureSpec with sample data...")
    
    try:
        from databricks.feature_engineering import FeatureEngineeringClient
        import pandas as pd
        from server import utils
        
        fe = FeatureEngineeringClient()
        
        # Get a sample sell_id from the database
        query = 'SELECT "SELL_ID" FROM excel_app.layout_data LIMIT 1'
        result = utils.execute_query(query)
        
        if not result:
            log("⚠️  No products found to test with")
            return
        
        sample_sell_id = result[0]['SELL_ID']
        log(f"→ Testing with sell_id: {sample_sell_id}")
        
        # Create a test lookup DataFrame
        lookup_df = pd.DataFrame({
            'sell_id': [sample_sell_id]
        })
        
        # Lookup features using the FeatureSpec
        log("→ Looking up features...")
        features_df = fe.read_table(
            name="main.excel_app.stock_optimization_features",
            lookup_keys=lookup_df
        )
        
        log("✓ Feature lookup successful!")
        log(f"   Columns: {list(features_df.columns)}")
        log(f"   Sample values:")
        for col in features_df.columns:
            log(f"     {col}: {features_df[col].iloc[0]}")
        
    except Exception as e:
        log(f"⚠️  Test failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    log("=" * 70)
    log("FEATURE SPEC CREATION")
    log("=" * 70)
    
    create_feature_spec()
    verify_feature_spec()
    test_feature_spec()
    
    log("=" * 70)
    log("FEATURE SPEC SETUP COMPLETE!")
    log("=" * 70)
    log("")
    log("Next steps:")
    log("1. Run: uv run python scripts/create_feature_serving_endpoint.py")
    log("2. Update MCP server to use Feature Serving")


if __name__ == "__main__":
    main()

