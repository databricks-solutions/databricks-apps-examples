#!/usr/bin/env python3
"""
Deploy Range Optimizer Model to Serving Endpoint

This script:
1. Verifies the model exists in Unity Catalog
2. Creates or updates a model serving endpoint
3. Tests the endpoint with sample data
"""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
)
from mlflow import MlflowClient
import mlflow
import pandas as pd
import requests
import time

# Configuration
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"
MODEL_NAME = "range_optimizer"
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

ENDPOINT_NAME = "range-optimizer-model"
WORKLOAD_SIZE = "Small"
SCALE_TO_ZERO = True


def main():
    """Main deployment function"""
    print("=" * 80)
    print("🚀 Deploying Range Optimizer to Serving Endpoint")
    print("=" * 80)

    # Initialize clients
    print("🔧 Initializing clients...")
    w = WorkspaceClient()
    mlflow.set_registry_uri("databricks-uc")
    client = MlflowClient()

    print(f"📦 Model: {UC_MODEL_PATH}")
    print(f"🔌 Endpoint: {ENDPOINT_NAME}")

    # Verify model exists
    print("\n🔍 Verifying model in Unity Catalog...")
    try:
        model = client.get_registered_model(UC_MODEL_PATH)
        versions = client.search_model_versions(f"name='{UC_MODEL_PATH}'")
        latest_version = max([int(v.version) for v in versions]) if versions else None

        print(f"✅ Model found: {UC_MODEL_PATH}")
        print(f"   Latest version: {latest_version}")

        # Try to get Champion alias
        try:
            champion = client.get_model_version_by_alias(UC_MODEL_PATH, "Champion")
            use_version = champion.version
            print(f"   Using Champion alias: v{use_version}")
        except:
            use_version = str(latest_version)
            print(f"   Using latest version: v{use_version}")

    except Exception as e:
        print(f"❌ Model not found: {e}")
        print("   Run train_model_standalone.py first!")
        return 1

    # Check if endpoint exists
    print("\n📍 Checking endpoint status...")
    try:
        existing = w.serving_endpoints.get(ENDPOINT_NAME)
        endpoint_exists = True
        print(f"   Endpoint '{ENDPOINT_NAME}' exists - will update")
    except:
        endpoint_exists = False
        print(f"   Endpoint '{ENDPOINT_NAME}' not found - will create new")

    # Create served entity config
    served_entity = ServedEntityInput(
        entity_name=UC_MODEL_PATH,
        entity_version=use_version,
        workload_size=WORKLOAD_SIZE,
        scale_to_zero_enabled=SCALE_TO_ZERO,
    )

    # Deploy endpoint
    print(f"\n{'🔄 Updating' if endpoint_exists else '🆕 Creating'} endpoint...")
    try:
        if endpoint_exists:
            w.serving_endpoints.update_config_and_wait(
                name=ENDPOINT_NAME,
                served_entities=[served_entity],
            )
            print("✅ Endpoint updated!")
        else:
            w.serving_endpoints.create_and_wait(
                name=ENDPOINT_NAME,
                config=EndpointCoreConfigInput(
                    name=ENDPOINT_NAME,
                    served_entities=[served_entity],
                )
            )
            print("✅ Endpoint created!")
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return 1

    # Get endpoint status
    print("\n📊 Endpoint Status:")
    endpoint = w.serving_endpoints.get(ENDPOINT_NAME)
    print(f"   Name: {endpoint.name}")
    print(f"   State: {endpoint.state.ready}")

    if endpoint.config and endpoint.config.served_entities:
        for entity in endpoint.config.served_entities:
            print(f"\n   Served Model:")
            print(f"     Model: {entity.entity_name}")
            print(f"     Version: {entity.entity_version}")
            print(f"     Workload: {entity.workload_size}")
            print(f"     Scale to Zero: {entity.scale_to_zero_enabled}")

    # Test the endpoint
    print("\n🧪 Testing endpoint...")
    test_data = pd.DataFrame([
        {'SKU_ID': 'SKU3001'},
        {'SKU_ID': 'SKU4001'},
        {'SKU_ID': 'SKU5001'},
    ])

    endpoint_url = f"{w.config.host}/serving-endpoints/{ENDPOINT_NAME}/invocations"
    payload = {"dataframe_records": test_data.to_dict(orient='records')}
    headers = {
        "Authorization": f"Bearer {w.config.token}",
        "Content-Type": "application/json"
    }

    print(f"   Calling: {ENDPOINT_NAME}")
    print(f"   Test SKUs: {test_data['SKU_ID'].tolist()}")

    try:
        response = requests.post(endpoint_url, json=payload, headers=headers, timeout=120)

        if response.status_code == 200:
            results = response.json()
            predictions = pd.DataFrame(results.get('predictions', []))

            print("✅ Endpoint test successful!")
            print(f"\n   Sample predictions ({len(predictions)} SKUs):")
            for _, row in predictions.iterrows():
                print(f"     • {row['sku_name']}: {row['current_facings']} → {row['recommended_facings']} facings ({row['change_from_current']})")

        else:
            print(f"⚠️  Endpoint returned status {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"⚠️  Test failed: {e}")
        print("   Note: Endpoint may still be initializing. Try again in a few moments.")

    # Print success summary
    print("\n" + "=" * 80)
    print("✅ SUCCESS! Model Deployed to Serving Endpoint")
    print("=" * 80)
    print(f"🔌 Endpoint: {ENDPOINT_NAME}")
    print(f"📦 Model: {UC_MODEL_PATH} (v{use_version})")
    print(f"🌐 URL: {w.config.host}/serving-endpoints/{ENDPOINT_NAME}")
    print("\nNext steps:")
    print("  1. Update MCP backend to use this endpoint")
    print("  2. Test optimization in UI app")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())
