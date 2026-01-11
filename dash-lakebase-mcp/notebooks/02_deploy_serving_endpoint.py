# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 Deploy Range Optimizer Serving Endpoint
# MAGIC 
# MAGIC This notebook deploys the registered Range Optimizer model with **Feature Store integration** to a **Model Serving endpoint** for real-time inference.
# MAGIC 
# MAGIC ## Schema Alignment
# MAGIC The deployed model uses the MCP app's schema:
# MAGIC - Input: `SKU_ID` (features auto-fetched from Feature Store)
# MAGIC - Output: Facings recommendations, profit metrics, change types
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
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"
MODEL_NAME = "range_optimizer"
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

# Serving endpoint settings
ENDPOINT_NAME = "range-optimizer-model"
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
# MAGIC **Important**: With Feature Store integration, we only need to provide `SKU_ID` and optionally `SKU_NAME`.
# MAGIC The endpoint will automatically fetch all other features from Unity Catalog!

# COMMAND ----------

# DBTITLE 1,Generate Test Data (Minimal)
import pandas as pd
import requests

# Test with just SKU IDs - features will be fetched automatically!
test_data = pd.DataFrame([
    {'SKU_ID': 'SKU3001', 'SKU_NAME': 'Stone & Wood Pacific Ale 6pk', 'CURRENT_FACINGS': 3},
    {'SKU_ID': 'SKU3009', 'SKU_NAME': 'White Claw Variety 12pk', 'CURRENT_FACINGS': 4},
    {'SKU_ID': 'SKU4001', 'SKU_NAME': 'Sriracha Original 455ml', 'CURRENT_FACINGS': 4},
    {'SKU_ID': 'SKU5001', 'SKU_NAME': "Ben & Jerry's Cookie Dough 458ml", 'CURRENT_FACINGS': 3},
    {'SKU_ID': 'SKU5012', 'SKU_NAME': 'Magnum Classic 4pk', 'CURRENT_FACINGS': 2},
])

print("📥 Test Data (SKU_IDs + current facings - other features auto-fetched):")
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
    display(result_df[['SKU_ID', 'SKU_NAME', 'CURRENT_FACINGS', 'RECOMMENDED_FACINGS', 'FACINGS_CHANGE', 'CHANGE_TYPE', 'EXPECTED_WEEKLY_PROFIT']])
    
    print("\n💰 Summary:")
    print(f"   Total Recommended Facings: {result_df['RECOMMENDED_FACINGS'].sum():.0f}")
    print(f"   Total Weekly Profit: ${result_df['EXPECTED_WEEKLY_PROFIT'].sum():,.2f}")
    print(f"   SKUs with Increased Facings: {len(result_df[result_df['CHANGE_TYPE'] == 'increased'])}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Test with What-If Scenarios
# MAGIC 
# MAGIC You can override specific features by including them in the request:

# COMMAND ----------

# DBTITLE 1,Test with What-If Overrides
# Override demand for what-if analysis
test_data_custom = pd.DataFrame([
    {
        'SKU_ID': 'SKU3001',
        'SKU_NAME': 'Stone & Wood Pacific Ale 6pk',
        'CURRENT_FACINGS': 3,
        'WEEKLY_UNITS': 150.0,  # Override: What if demand increases?
        'DEMAND_STD': 40.0      # Override: Higher volatility
    },
])

print("📥 Test with Custom Feature Values (What-If):")
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
    
    print("\n📤 What-If Results (with increased demand):")
    display(result_custom_df[['SKU_ID', 'SKU_NAME', 'WEEKLY_UNITS', 'RECOMMENDED_FACINGS', 'EXPECTED_WEEKLY_PROFIT']])
    
    print("\n💡 Impact of Demand Increase:")
    print(f"   Recommended Facings: {result_custom_df['RECOMMENDED_FACINGS'].iloc[0]:.0f}")
    print(f"   Expected Weekly Profit: ${result_custom_df['EXPECTED_WEEKLY_PROFIT'].iloc[0]:,.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Deployment Complete!
# MAGIC 
# MAGIC **Serving endpoint is now live with automatic feature lookup!**
# MAGIC 
# MAGIC | Property | Value |
# MAGIC |----------|-------|
# MAGIC | Endpoint | `range-optimizer-model` |
# MAGIC | Model | `main.stock_optimization.range_optimizer` |
# MAGIC | Feature Store | ✅ Enabled |
# MAGIC 
# MAGIC ### ✨ Key Features
# MAGIC 
# MAGIC 1. **Automatic Feature Lookup**: Only send `SKU_ID`, features fetched from UC
# MAGIC 2. **Real-time Inference**: Low-latency predictions
# MAGIC 3. **Auto-scaling**: Scales to zero when idle
# MAGIC 
# MAGIC ### Usage Examples
# MAGIC 
# MAGIC **Python (Minimal Input):**
# MAGIC ```python
# MAGIC import requests
# MAGIC import pandas as pd
# MAGIC 
# MAGIC # Only need SKU IDs!
# MAGIC data = pd.DataFrame([
# MAGIC     {'SKU_ID': 'SKU3001', 'SKU_NAME': 'Stone & Wood Pacific Ale 6pk', 'CURRENT_FACINGS': 3},
# MAGIC     {'SKU_ID': 'SKU4001', 'SKU_NAME': 'Sriracha Original 455ml', 'CURRENT_FACINGS': 4},
# MAGIC ])
# MAGIC 
# MAGIC response = requests.post(
# MAGIC     f"{workspace_url}/serving-endpoints/range-optimizer-model/invocations",
# MAGIC     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
# MAGIC     json={"dataframe_records": data.to_dict(orient='records')}
# MAGIC )
# MAGIC results = response.json()
# MAGIC ```
# MAGIC 
# MAGIC **Output Schema:**
# MAGIC ```json
# MAGIC {
# MAGIC   "SKU_ID": "SKU3001",
# MAGIC   "SKU_NAME": "Stone & Wood Pacific Ale 6pk",
# MAGIC   "CATEGORY": "Beer & Seltzer",
# MAGIC   "RECOMMENDED_FACINGS": 4,
# MAGIC   "FACINGS_CHANGE": 1,
# MAGIC   "CHANGE_TYPE": "increased",
# MAGIC   "EXPECTED_WEEKLY_PROFIT": 816.00,
# MAGIC   "IS_RANGED": true
# MAGIC }
# MAGIC ```
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Test with MCP App**: Point UI to this endpoint
# MAGIC 2. **Monitor**: View metrics in Serving UI
# MAGIC 3. **Analyze Results**: Run `03_analyze_optimization_results` notebook

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗑️ Cleanup (Optional)

# COMMAND ----------

# # Uncomment to delete endpoint
# # DELETE_ENDPOINT = True
# 
# # if DELETE_ENDPOINT:
# #     print(f"🗑️ Deleting endpoint '{ENDPOINT_NAME}'...")
# #     w.serving_endpoints.delete(ENDPOINT_NAME)
# #     print("✅ Endpoint deleted")
