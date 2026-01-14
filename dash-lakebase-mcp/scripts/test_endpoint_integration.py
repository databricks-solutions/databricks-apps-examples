#!/usr/bin/env python3
"""
Test Feature Store + Serving Endpoint Integration

This script tests the complete flow:
1. Load features from Feature Store
2. Call serving endpoint
3. Validate results
"""

import pandas as pd
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.runtime import spark

# Configuration
ENDPOINT_NAME = "range-optimizer-model"
SKU_FEATURES_TABLE = "smarter_forecasting.stock_optimization.sku_features"
DEMAND_FEATURES_TABLE = "smarter_forecasting.stock_optimization.demand_features"


def test_endpoint_integration():
    """Test the complete integration"""
    print("=" * 80)
    print("🧪 Testing Feature Store + Serving Endpoint Integration")
    print("=" * 80)

    # Initialize client
    print("\n🔧 Initializing Workspace Client...")
    w = WorkspaceClient()

    # Test SKUs
    test_skus = ["SKU3001", "SKU4001", "SKU5001"]
    print(f"\n📦 Testing with SKUs: {test_skus}")

    # Step 1: Fetch features from Feature Store
    print("\n📊 Step 1: Fetching features from Feature Store...")
    sku_ids_str = "','".join(test_skus)

    features_query = f"""
        SELECT
            p.SKU_ID,
            p.SKU_NAME,
            p.UNIT_COST,
            p.UNIT_PRICE,
            p.CATEGORY,
            p.SEGMENT,
            p.BRAND,
            p.PACK_WIDTH_MM,
            p.IS_MUST_STOCK,
            p.IS_PRIVATE_LABEL,
            p.CURRENT_FACINGS,
            d.WEEKLY_UNITS,
            d.DEMAND_STD,
            d.FORECAST_4W
        FROM {SKU_FEATURES_TABLE} p
        JOIN {DEMAND_FEATURES_TABLE} d ON p.SKU_ID = d.SKU_ID
        WHERE p.SKU_ID IN ('{sku_ids_str}')
    """

    features_df = spark.sql(features_query).toPandas()
    print(f"✅ Fetched features for {len(features_df)} SKUs")
    print(f"   Columns: {list(features_df.columns)}")
    print(f"\n   Sample data:")
    for _, row in features_df.head(1).iterrows():
        print(f"     SKU: {row['SKU_ID']} - {row['SKU_NAME']}")
        print(f"     Price: ${row['UNIT_PRICE']}, Cost: ${row['UNIT_COST']}")
        print(f"     Weekly Units: {row['WEEKLY_UNITS']}, Demand Std: {row['DEMAND_STD']}")

    # Step 2: Call serving endpoint
    print(f"\n🌐 Step 2: Calling serving endpoint: {ENDPOINT_NAME}...")
    endpoint_url = f"{w.config.host}/serving-endpoints/{ENDPOINT_NAME}/invocations"

    payload = {
        "dataframe_records": features_df.to_dict(orient='records')
    }

    headers = {
        "Authorization": f"Bearer {w.config.token}",
        "Content-Type": "application/json"
    }

    response = requests.post(endpoint_url, json=payload, headers=headers, timeout=120)

    if response.status_code != 200:
        print(f"❌ Endpoint returned error: {response.status_code}")
        print(f"   Response: {response.text}")
        return 1

    # Step 3: Parse and validate results
    print("✅ Endpoint call successful!")
    results = response.json()
    predictions_df = pd.DataFrame(results.get('predictions', []))

    print(f"\n📈 Step 3: Parsing optimization results...")
    print(f"   Received {len(predictions_df)} predictions")

    # Display results
    print(f"\n🎯 Optimization Results:")
    print("=" * 80)

    for _, row in predictions_df.iterrows():
        change_emoji = "📈" if row['facings_change'] > 0 else "📉" if row['facings_change'] < 0 else "➡️"
        print(f"\n{change_emoji} {row['sku_name']}")
        print(f"   Category: {row['category']} | Brand: {row['brand']}")
        print(f"   Current Facings: {row['current_facings']} → Recommended: {row['recommended_facings']}")
        print(f"   Change: {row['facings_change']:+d} ({row['change_from_current']})")
        print(f"   Expected Weekly Margin: ${row['expected_margin_weekly']:.2f}")
        print(f"   Space Productivity: ${row['space_productivity']:.2f}/mm")
        print(f"   Confidence Score: {row['score']:.2%}")

    # Summary stats
    print(f"\n📊 Summary Statistics:")
    print("=" * 80)
    total_facings_change = predictions_df['facings_change'].sum()
    products_increased = (predictions_df['facings_change'] > 0).sum()
    products_decreased = (predictions_df['facings_change'] < 0).sum()
    products_unchanged = (predictions_df['facings_change'] == 0).sum()
    avg_margin = predictions_df['expected_margin_weekly'].mean()

    print(f"   Total Products: {len(predictions_df)}")
    print(f"   Products to Increase: {products_increased}")
    print(f"   Products to Decrease: {products_decreased}")
    print(f"   Products Unchanged: {products_unchanged}")
    print(f"   Net Facings Change: {total_facings_change:+d}")
    print(f"   Average Weekly Margin: ${avg_margin:.2f}")

    # Validation
    print(f"\n✅ Validation Checks:")
    print("=" * 80)
    checks_passed = 0
    checks_total = 0

    # Check 1: All SKUs returned
    checks_total += 1
    if len(predictions_df) == len(test_skus):
        print(f"   ✅ All {len(test_skus)} SKUs returned")
        checks_passed += 1
    else:
        print(f"   ❌ Expected {len(test_skus)} SKUs, got {len(predictions_df)}")

    # Check 2: Required columns present
    checks_total += 1
    required_cols = ['sku_id', 'recommended_facings', 'facings_change', 'expected_margin_weekly']
    missing_cols = [col for col in required_cols if col not in predictions_df.columns]
    if not missing_cols:
        print(f"   ✅ All required columns present")
        checks_passed += 1
    else:
        print(f"   ❌ Missing columns: {missing_cols}")

    # Check 3: Valid recommendations
    checks_total += 1
    invalid_facings = predictions_df[predictions_df['recommended_facings'] < 0]
    if len(invalid_facings) == 0:
        print(f"   ✅ All recommendations are valid (>= 0)")
        checks_passed += 1
    else:
        print(f"   ❌ Found {len(invalid_facings)} invalid recommendations")

    # Check 4: Reasonable margins
    checks_total += 1
    valid_margins = predictions_df['expected_margin_weekly'] > 0
    if valid_margins.all():
        print(f"   ✅ All margins are positive")
        checks_passed += 1
    else:
        print(f"   ⚠️  {(~valid_margins).sum()} products have zero/negative margins")

    print(f"\n🎯 Validation Result: {checks_passed}/{checks_total} checks passed")

    # Final status
    print("\n" + "=" * 80)
    if checks_passed == checks_total:
        print("✅ SUCCESS! Feature Store + Serving Endpoint Integration Working!")
    else:
        print("⚠️  PARTIAL SUCCESS - Some validation checks failed")
    print("=" * 80)

    print(f"\n📝 Integration Details:")
    print(f"   Feature Store Tables:")
    print(f"     • {SKU_FEATURES_TABLE}")
    print(f"     • {DEMAND_FEATURES_TABLE}")
    print(f"   Serving Endpoint: {ENDPOINT_NAME}")
    print(f"   Model: smarter_forecasting.stock_optimization.range_optimizer")
    print(f"\n💡 Next Steps:")
    print(f"   1. Update MCP backend router.py with this integration code")
    print(f"   2. Test via UI app optimization flow")
    print(f"   3. View results in planogram page")

    return 0 if checks_passed == checks_total else 1


if __name__ == "__main__":
    exit(test_endpoint_integration())
