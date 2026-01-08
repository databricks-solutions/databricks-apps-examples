# Unity Catalog Metastore Configuration Guide

## Current Status: ⏳ Waiting for Metastore Storage Configuration

### Problem
Your Unity Catalog metastore (ID: `c9c3d288-093a-4d9d-9532-56be920fa4e5`) does not have a root storage credential configured. This prevents model artifact uploads to Unity Catalog.

**Error**:
```
DAC_DOES_NOT_EXIST: Root storage credential for metastore c9c3d288-093a-4d9d-9532-56be920fa4e5 does not exist.
```

### What's Already Set Up ✅

1. **Unity Catalog Catalog Created**:
   - Name: `coles_inventory`
   - Type: MANAGED_CATALOG
   - Owner: david.okeeffe@databricks.com

2. **Schema Created**:
   - Name: `coles_inventory.models`
   - Purpose: ML models for stock optimization

3. **Model Deployment Script Ready**:
   - Model name: `coles_inventory.models.stock_optimization_model`
   - MLflow tracking configured
   - Unity Catalog registry URI set

4. **Application Code Ready**:
   - Hybrid optimizer configured
   - Will automatically use MLflow endpoint once deployed

---

## Required: Metastore Storage Configuration

### Prerequisites (Workspace Admin Required)

You need **Metastore Admin** or **Account Admin** privileges to configure the metastore storage.

### Step-by-Step Configuration

#### Option A: Using Databricks UI (Recommended)

1. **Navigate to Metastore Settings**:
   ```
   Databricks Workspace → Data → (Three dots menu) → Manage Unity Catalog → Metastores
   ```

2. **Select Your Metastore**:
   - Click on the metastore (likely named "primary" or your workspace name)
   - Metastore ID should be: `c9c3d288-093a-4d9d-9532-56be920fa4e5`

3. **Create Storage Credential** (Azure):
   - Go to: Data → Storage Credentials → Create Credential
   - Name: `coles_inventory_storage_cred` (or any name)
   - Type: Azure Storage Account
   - **Authentication Method**: Choose one:

     **A) Managed Identity (Recommended)**:
     ```
     - Use workspace's managed identity
     - Enable for Unity Catalog
     ```

     **B) Service Principal**:
     ```
     - Directory (Tenant) ID: <your-azure-tenant-id>
     - Application (Client) ID: <your-app-id>
     - Client Secret: <your-secret>
     ```

     **C) Storage Account Key**:
     ```
     - Storage Account Name: <your-storage-account>
     - Access Key: <your-access-key>
     ```

4. **Grant Storage Credential Permissions**:
   ```
   - Grant READ FILES and WRITE FILES permissions to Unity Catalog
   ```

5. **Configure Metastore Root Storage**:
   - Go back to Metastore settings
   - Click "Edit" next to "Root storage location"
   - Set to your Azure storage path:
     ```
     abfss://<container>@<storage-account>.dfs.core.windows.net/unity-catalog/metastore
     ```
   - Select the storage credential you just created

6. **Save and Test**:
   - Click "Save"
   - Test access by creating a test table in Unity Catalog

#### Option B: Using Databricks CLI

```bash
# 1. Create storage credential
databricks storage-credentials create coles_inventory_storage_cred \
  --read-only false \
  --azure-managed-identity '{
    "access_connector_id": "/subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.Databricks/accessConnectors/<connector-name>"
  }'

# 2. Update metastore with root storage
databricks metastores update c9c3d288-093a-4d9d-9532-56be920fa4e5 \
  --storage-root "abfss://<container>@<storage-account>.dfs.core.windows.net/unity-catalog/metastore" \
  --storage-root-credential-id <credential-id-from-step-1>
```

#### Option C: Using Databricks SDK (Python)

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import (
    StorageCredentialInfo,
    AzureManagedIdentity,
    UpdateMetastore
)

w = WorkspaceClient()

# 1. Create storage credential
credential = w.storage_credentials.create(
    name="coles_inventory_storage_cred",
    azure_managed_identity=AzureManagedIdentity(
        access_connector_id="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Databricks/accessConnectors/<name>"
    ),
    read_only=False
)

# 2. Update metastore
w.metastores.update(
    id="c9c3d288-093a-4d9d-9532-56be920fa4e5",
    storage_root="abfss://<container>@<storage-account>.dfs.core.windows.net/unity-catalog/metastore",
    storage_root_credential_id=credential.id
)
```

---

## Verification Steps

After configuration, verify the setup:

### 1. Check Metastore Status
```bash
databricks metastores get c9c3d288-093a-4d9d-9532-56be920fa4e5
```

Look for:
```json
{
  "storage_root": "abfss://...",
  "storage_root_credential_id": "...",
  "storage_root_credential_name": "..."
}
```

### 2. Test with Sample Model
```python
import mlflow
mlflow.set_registry_uri("databricks-uc")

# Try creating a test model
with mlflow.start_run():
    mlflow.log_param("test", "value")
    mlflow.sklearn.log_model(
        sklearn_model=None,  # Dummy model
        artifact_path="model",
        registered_model_name="coles_inventory.models.test_model"
    )
```

If this succeeds without errors, your metastore is properly configured!

---

## Once Configured: Deploy the Model

After the metastore has storage configured, run:

```bash
# 1. Deploy model to Unity Catalog
cd /Users/david.okeeffe/Repos/databricks-apps-examples/dash-dbx-writeback
uv run python deploy_model_to_mlflow.py
```

Expected output:
```
✓ Model logged with run_id: <run-id>
✓ Model registered in Unity Catalog: coles_inventory.models.stock_optimization_model
```

```bash
# 2. Create serving endpoint via DABs
databricks bundle deploy -t azure-east
```

This will:
- ✅ Create model version 1 in Unity Catalog
- ✅ Deploy serving endpoint with the UC model
- ✅ Enable the Coles app to use MLflow for optimization

---

## Architecture After Setup

```
Unity Catalog Metastore
  ├─ Storage Credential (Azure)
  ├─ Root Storage Location (abfss://...)
  └─ Catalog: coles_inventory
      └─ Schema: models
          └─ Model: stock_optimization_model
              └─ Version 1
                  ├─ Artifacts (stored in metastore storage)
                  ├─ Signature (input/output schema)
                  └─ Serving Endpoint
                      └─ Used by Coles Inventory Intelligence app
```

---

## Troubleshooting

### Issue: "DAC_DOES_NOT_EXIST"
**Solution**: Metastore needs storage credential configured (see above)

### Issue: "PERMISSION_DENIED"
**Solution**: Ensure service principal has:
- `Storage Blob Data Contributor` on Azure storage account
- `USE CATALOG` and `CREATE MODEL` on Unity Catalog

### Issue: "INVALID_STATE"
**Solution**: Storage credential must be active and accessible

### Issue: Can't find metastore settings
**Solution**: You need Metastore Admin role. Contact your Databricks account admin.

---

## Checklist

Before deploying the model, ensure:

- [ ] Metastore has storage credential configured
- [ ] Metastore has root storage location set
- [ ] Storage credential has proper Azure permissions
- [ ] Catalog `coles_inventory` exists and is accessible
- [ ] Schema `coles_inventory.models` exists
- [ ] You can create test tables in `coles_inventory.models`
- [ ] MLflow tracking URI set to `databricks`
- [ ] MLflow registry URI set to `databricks-uc`

---

## Contact Information

**If you need help**:
1. Contact your Databricks workspace admin
2. Reference this metastore ID: `c9c3d288-093a-4d9d-9532-56be920fa4e5`
3. Share this document with them

**Documentation Links**:
- [Unity Catalog Storage Credentials](https://docs.databricks.com/data-governance/unity-catalog/manage-external-locations-and-credentials.html)
- [Unity Catalog Metastores](https://docs.databricks.com/data-governance/unity-catalog/create-metastore.html)
- [Unity Catalog Models](https://docs.databricks.com/machine-learning/manage-model-lifecycle/index.html)

---

## Current Files Ready for Deployment

All code is ready and waiting for metastore configuration:

1. **setup_unity_catalog.py** - Creates catalog and schema ✅
2. **deploy_model_to_mlflow.py** - Registers model in UC (waiting for storage)
3. **resources/model_serving.yml** - DAB config for endpoint
4. **Application code** - Hybrid optimizer ready

**Next step**: Configure metastore storage, then run deployment script.

---

**Status**: ⏳ **Waiting for metastore storage credential configuration**

Once configured, deployment will take ~2-3 minutes and the app will automatically use the MLflow endpoint.
