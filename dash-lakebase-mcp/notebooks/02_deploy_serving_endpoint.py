# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 Deploy Stock Optimization Serving Endpoint
# MAGIC 
# MAGIC This notebook deploys the registered Stock Optimization model with **Feature Store integration** to a **Model Serving endpoint** for real-time inference.
# MAGIC 
# MAGIC ## Key Features
# MAGIC - Automatic feature lookup from Unity Catalog
# MAGIC - Real-time optimization inference
# MAGIC - Scalable serving with auto-scaling
# MAGIC 
# MAGIC ## Prerequisites
# MAGIC - Feature tables created (`00_create_feature_tables`)
# MAGIC - Model trained and registered (`01_train_stock_optimizer`)
# MAGIC - Permissions to create serving endpoints

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
# Must match the model from notebook 01
CATALOG = "main"
SCHEMA = "stock_optimization"
MODEL_NAME = "stock_optimizer"
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

# Serving endpoint settings
ENDPOINT_NAME = "stock-optimization-model"
WORKLOAD_SIZE = "Small"  # Small, Medium, or Large
SCALE_TO_ZERO = True     # Scale to zero when idle (saves cost)

print(f"📦 Model: {UC_MODEL_PATH}")
print(f"🔌 Endpoint: {ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔍 Verify Model Exists

# COMMAND ----------

# DBTITLE 1,Check Model in Unity Catalog
from mlflow import MlflowClient
import mlflow

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()

try:
    model = client.get_registered_model(UC_MODEL_PATH)
    versions = client.search_model_versions(f"name='{UC_MODEL_PATH}'")
    latest_version = max([int(v.version) for v in versions]) if versions else None
    
    print(f"✅ Model found: {UC_MODEL_PATH}")
    print(f"   Latest version: {latest_version}")
    
    try:
        prod_version = client.get_model_version_by_alias(UC_MODEL_PATH, "production")
        print(f"   Production alias: v{prod_version.version}")
        use_version = prod_version.version
    except:
        print("   Production alias: Not set - using latest")
        use_version = latest_version
        
except Exception as e:
    print(f"❌ Model not found: {e}")
    print("\n👉 Please run notebooks 00 and 01 first!")
    dbutils.notebook.exit("Model not found")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 Deploy Serving Endpoint

# COMMAND ----------

# DBTITLE 1,Setup Workspace Client
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
)

w = WorkspaceClient()

# Check if endpoint exists
try:
    existing = w.serving_endpoints.get(ENDPOINT_NAME)
    endpoint_exists = True
    print(f"📍 Endpoint '{ENDPOINT_NAME}' exists - will update")
except:
    endpoint_exists = False
    print(f"📍 Endpoint '{ENDPOINT_NAME}' not found - will create new")

# COMMAND ----------

# DBTITLE 1,Create/Update Endpoint
# Define served entity
served_entity = ServedEntityInput(
    entity_name=UC_MODEL_PATH,
    entity_version=str(use_version),
    workload_size=WORKLOAD_SIZE,
    scale_to_zero_enabled=SCALE_TO_ZERO,
)

if endpoint_exists:
    print(f"🔄 Updating endpoint '{ENDPOINT_NAME}'...")
    w.serving_endpoints.update_config_and_wait(
        name=ENDPOINT_NAME,
        served_entities=[served_entity],
    )
    print("✅ Endpoint updated!")
else:
    print(f"🆕 Creating endpoint '{ENDPOINT_NAME}'...")
    w.serving_endpoints.create_and_wait(
        name=ENDPOINT_NAME,
        config=EndpointCoreConfigInput(
            served_entities=[served_entity],
        )
    )
    print("✅ Endpoint created!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Endpoint Status

# COMMAND ----------

# DBTITLE 1,Check Endpoint Status
endpoint = w.serving_endpoints.get(ENDPOINT_NAME)

print(f"🔌 Endpoint: {endpoint.name}")
print(f"   State: {endpoint.state.ready}")

if endpoint.config and endpoint.config.served_entities:
    for entity in endpoint.config.served_entities:
        print(f"\n📦 Served Entity:")
        print(f"   Model: {entity.entity_name}")
        print(f"   Version: {entity.entity_version}")
        print(f"   Workload: {entity.workload_size}")
        print(f"   Scale to Zero: {entity.scale_to_zero_enabled}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Test the Endpoint with Feature Store
# MAGIC 
# MAGIC **Important**: With Feature Store integration, we only need to provide `SELL_ID` and optionally `PRODUCT_NAME`.
# MAGIC The endpoint will automatically fetch all other features from Unity Catalog!

# COMMAND ----------

# DBTITLE 1,Generate Test Data (Minimal)
import pandas as pd
import requests

# Test with just product IDs - features will be fetched automatically!
test_data = pd.DataFrame([
    {'SELL_ID': 'SKU4001', 'PRODUCT_NAME': 'Stone & Wood Pacific Ale 6pk'},
    {'SELL_ID': 'SKU4004', 'PRODUCT_NAME': 'White Claw Variety 12pk'},
    {'SELL_ID': 'SKU4006', 'PRODUCT_NAME': 'Sriracha Original 455ml'},
    {'SELL_ID': 'SKU4011', 'PRODUCT_NAME': "Ben & Jerry's Cookie Dough 458ml"},
    {'SELL_ID': 'SKU4015', 'PRODUCT_NAME': 'Magnum Double Caramel 4pk'},
])

print("📥 Test Data (only IDs - features auto-fetched):")
display(test_data)

# COMMAND ----------

# DBTITLE 1,Call Endpoint
# Get auth details
workspace_url = w.config.host
token = w.config.token

# Call endpoint
endpoint_url = f"{workspace_url}/serving-endpoints/{ENDPOINT_NAME}/invocations"

payload = {
    "dataframe_records": test_data.to_dict(orient='records')
}

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print(f"🌐 Calling endpoint: {ENDPOINT_NAME}")
print("   Features will be automatically fetched from Unity Catalog...")

response = requests.post(endpoint_url, json=payload, headers=headers, timeout=120)

if response.status_code == 200:
    print("✅ Endpoint responded successfully!")
    
    result = response.json()
    if isinstance(result, dict) and "predictions" in result:
        result_df = pd.DataFrame(result["predictions"])
    elif isinstance(result, list):
        result_df = pd.DataFrame(result)
    else:
        result_df = pd.DataFrame([result])
    
    print("\n📤 Optimization Results:")
    display(result_df[['SELL_ID', 'PRODUCT_NAME', 'OPTIMAL_ORDER_QTY', 'SAFETY_STOCK', 'REORDER_POINT', 'EXPECTED_ANNUAL_PROFIT']])
    
    print("\n💰 Summary:")
    print(f"   Total Optimal Stock: {result_df['OPTIMAL_ORDER_QTY'].sum():,.0f} units")
    print(f"   Total Safety Stock: {result_df['SAFETY_STOCK'].sum():,.0f} units")
    print(f"   Total Expected Profit: ${result_df['EXPECTED_ANNUAL_PROFIT'].sum():,.2f}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Test with Custom Feature Values
# MAGIC 
# MAGIC You can also override specific features by including them in the request:

# COMMAND ----------

# DBTITLE 1,Test with Custom Overrides
# Override demand forecasts for what-if analysis
test_data_custom = pd.DataFrame([
    {
        'SELL_ID': 'SKU4001',
        'PRODUCT_NAME': 'Stone & Wood Pacific Ale 6pk',
        'AVG_DAILY_DEMAND': 200.0,  # Override: What if demand increases?
        'DEMAND_STD': 45.0           # Override: Higher volatility
    },
])

print("📥 Test with Custom Feature Values:")
display(test_data_custom)

payload_custom = {
    "dataframe_records": test_data_custom.to_dict(orient='records')
}

response_custom = requests.post(endpoint_url, json=payload_custom, headers=headers, timeout=120)

if response_custom.status_code == 200:
    result_custom = response_custom.json()
    if isinstance(result_custom, dict) and "predictions" in result_custom:
        result_custom_df = pd.DataFrame(result_custom["predictions"])
    elif isinstance(result_custom, list):
        result_custom_df = pd.DataFrame(result_custom)
    else:
        result_custom_df = pd.DataFrame([result_custom])
    
    print("\n📤 Optimization Results (with custom demand):")
    display(result_custom_df[['SELL_ID', 'PRODUCT_NAME', 'AVG_DAILY_DEMAND', 'OPTIMAL_ORDER_QTY', 'SAFETY_STOCK']])
    
    print("\n💡 Impact of Demand Increase:")
    print(f"   Optimal Order Qty: {result_custom_df['OPTIMAL_ORDER_QTY'].iloc[0]:,.0f} units")
    print(f"   Safety Stock: {result_custom_df['SAFETY_STOCK'].iloc[0]:,.0f} units")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Deployment Complete!
# MAGIC 
# MAGIC **Serving endpoint is now live with automatic feature lookup!**
# MAGIC 
# MAGIC | Property | Value |
# MAGIC |----------|-------|
# MAGIC | Endpoint | `stock-optimization-model` |
# MAGIC | Model | `main.stock_optimization.stock_optimizer` |
# MAGIC | Version | `{use_version}` |
# MAGIC | Feature Store | ✅ Enabled |
# MAGIC 
# MAGIC ### ✨ Key Features
# MAGIC 
# MAGIC 1. **Automatic Feature Lookup**: Only send `SELL_ID`, features fetched from UC
# MAGIC 2. **Real-time Inference**: Low-latency predictions
# MAGIC 3. **Auto-scaling**: Scales to zero when idle
# MAGIC 4. **Feature Consistency**: Always uses latest feature definitions
# MAGIC 
# MAGIC ### Usage Examples
# MAGIC 
# MAGIC **Python (Minimal Input):**
# MAGIC ```python
# MAGIC import requests
# MAGIC 
# MAGIC # Only need product IDs!
# MAGIC data = pd.DataFrame([
# MAGIC     {'SELL_ID': 'SKU4001', 'PRODUCT_NAME': 'Stone & Wood Pacific Ale 6pk'},
# MAGIC     {'SELL_ID': 'SKU4002', 'PRODUCT_NAME': 'Balter XPA 4pk'},
# MAGIC ])
# MAGIC 
# MAGIC response = requests.post(
# MAGIC     f"{workspace_url}/serving-endpoints/stock-optimization-model/invocations",
# MAGIC     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
# MAGIC     json={"dataframe_records": data.to_dict(orient='records')}
# MAGIC )
# MAGIC results = response.json()
# MAGIC ```
# MAGIC 
# MAGIC **Python (with Custom Overrides):**
# MAGIC ```python
# MAGIC # Override specific features for what-if analysis
# MAGIC data = pd.DataFrame([{
# MAGIC     'SELL_ID': 'SKU4001',
# MAGIC     'AVG_DAILY_DEMAND': 250.0,  # What if demand increases?
# MAGIC     'DEMAND_STD': 50.0           # With higher volatility?
# MAGIC }])
# MAGIC 
# MAGIC response = requests.post(endpoint_url, json={"dataframe_records": data.to_dict(orient='records')})
# MAGIC ```
# MAGIC 
# MAGIC **cURL:**
# MAGIC ```bash
# MAGIC curl -X POST \
# MAGIC   -H "Authorization: Bearer $TOKEN" \
# MAGIC   -H "Content-Type: application/json" \
# MAGIC   -d '{"dataframe_records": [{"SELL_ID": "SKU4001", "PRODUCT_NAME": "Stone & Wood Pacific Ale 6pk"}]}' \
# MAGIC   https://<workspace>/serving-endpoints/stock-optimization-model/invocations
# MAGIC ```
# MAGIC 
# MAGIC ### Monitoring
# MAGIC 
# MAGIC View endpoint metrics in:
# MAGIC - **Serving UI**: Workspace → Serving → stock-optimization-model
# MAGIC - **Metrics**: Request rate, latency, error rate
# MAGIC - **Logs**: Request/response logs

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗑️ Cleanup (Optional)
# MAGIC 
# MAGIC Uncomment to delete the endpoint:

# COMMAND ----------

# # Uncomment to delete endpoint
# # DELETE_ENDPOINT = True
# 
# # if DELETE_ENDPOINT:
# #     print(f"🗑️ Deleting endpoint '{ENDPOINT_NAME}'...")
# #     w.serving_endpoints.delete(ENDPOINT_NAME)
# #     print("✅ Endpoint deleted")
