# 🚀 ML Notebooks Deployment Guide

Deploy and run ML notebooks as **serverless Databricks jobs**.

## 📋 Prerequisites

1. **Databricks CLI** installed and configured:
```bash
# Install
pip install databricks-cli

# Configure (if not already done)
databricks configure --token
# Enter your workspace URL and token
```

2. **Environment Variables** (optional):
```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-token"
```

3. **Permissions**:
   - CREATE on Catalog (for feature tables)
   - CREATE MODEL on Schema
   - CREATE SERVING ENDPOINT

## 🚀 Quick Deploy & Run

### One-Step: Deploy and Run Full Pipeline

```bash
cd notebooks/

# Deploy notebooks and jobs
./deploy.sh

# Run the full ML pipeline (all 3 notebooks in sequence)
./run-pipeline.sh
```

That's it! The pipeline will:
1. ✅ Create feature tables in Unity Catalog
2. ✅ Train the stock optimization model
3. ✅ Deploy the serving endpoint

Monitor progress in: **Workflows → Jobs → [dev] Full ML Pipeline**

## 📖 Detailed Usage

### Deploy Notebooks

```bash
cd notebooks/
./deploy.sh
```

This will:
- Validate the bundle configuration
- Upload notebooks to your workspace
- Create 4 serverless jobs:
  1. `[dev] 00 - Create Feature Tables`
  2. `[dev] 01 - Train Stock Optimizer`
  3. `[dev] 02 - Deploy Serving Endpoint`
  4. `[dev] Full ML Pipeline` (runs all in sequence)

### Run Jobs

#### Run Full Pipeline (Recommended)

```bash
./run-pipeline.sh
```

Runs all notebooks in sequence with proper dependencies.

#### Run Individual Steps

```bash
# Create feature tables only
./run-pipeline.sh --job create_feature_tables

# Train model only (requires feature tables)
./run-pipeline.sh --job train_stock_optimizer

# Deploy endpoint only (requires trained model)
./run-pipeline.sh --job deploy_serving_endpoint
```

#### Custom Configuration

```bash
# Use different catalog/schema
./run-pipeline.sh --catalog prod --schema inventory

# Combine options
./run-pipeline.sh --catalog prod --schema inventory --job train_stock_optimizer
```

### Using Databricks CLI Directly

```bash
# List deployed jobs
databricks bundle resources list

# Run specific job
databricks bundle run full_ml_pipeline

# With custom parameters
databricks bundle run full_ml_pipeline \
    --var="catalog=prod" \
    --var="schema=inventory"

# Check job status
databricks jobs list-runs --job-id <job-id>
```

## 📊 Job Configurations

### Full ML Pipeline
- **Duration**: ~15-20 minutes
- **Tasks**: 3 sequential tasks
- **Cluster**: Serverless (auto-provisioned)
- **Runtime**: Databricks Runtime 14.3 ML

**Task Flow**:
```
create_features → train_model → deploy_endpoint
```

### Individual Jobs
Each can be run independently:

**1. Create Feature Tables**
- Creates `product_features` and `demand_features` tables
- Runtime: ~5 minutes

**2. Train Stock Optimizer**
- Trains EOQ model with Feature Store integration
- Registers to Unity Catalog
- Runtime: ~5 minutes

**3. Deploy Serving Endpoint**
- Creates/updates serving endpoint
- Configures auto-scaling
- Runtime: ~3-5 minutes

## 🔧 Configuration

### Update Catalog/Schema

Edit `notebooks/databricks.yml`:

```yaml
variables:
  catalog:
    description: Unity Catalog name
    default: main  # ← Change this
  
  schema:
    description: Schema name
    default: stock_optimization  # ← Change this
```

### Update Cluster Configuration

Edit `notebooks/databricks.yml` under `job_clusters`:

```yaml
job_clusters:
  - job_cluster_key: ml_cluster
    new_cluster:
      spark_version: 14.3.x-cpu-ml-scala2.12
      node_type_id: i3.xlarge  # ← Change instance type
      num_workers: 0  # 0 = serverless
      data_security_mode: SINGLE_USER
      runtime_engine: PHOTON
```

## 📍 Notebook Locations

After deployment, notebooks are in:
```
/Workspace/Users/<your-email>/stock_optimization_ml/
├── 00_create_feature_tables.py
├── 01_train_stock_optimizer.py
└── 02_deploy_serving_endpoint.py
```

## 📈 Monitoring

### View Job Runs

1. Open Databricks workspace
2. Navigate to: **Workflows → Jobs**
3. Find: `[dev] Full ML Pipeline`
4. Click to view run history and logs

### View Job Logs

```bash
# Get recent runs
databricks jobs list-runs --limit 5

# Get specific run details
databricks jobs get-run --run-id <run-id>

# Get run output
databricks jobs get-run-output --run-id <run-id>
```

### Check Resources Created

```bash
# View feature tables
databricks unity-catalog tables list \
    --catalog main \
    --schema stock_optimization

# View models
databricks unity-catalog models list \
    --catalog main \
    --schema stock_optimization

# View serving endpoints
databricks serving-endpoints list
```

## 🎯 Expected Results

After successful pipeline run:

### Feature Tables Created
```
✅ main.stock_optimization.product_features (15 products)
✅ main.stock_optimization.demand_features (15 products)
```

### Model Registered
```
✅ main.stock_optimization.stock_optimizer
   ├── Version 1 (@production, @champion)
   └── Lineage: product_features, demand_features
```

### Serving Endpoint Deployed
```
✅ stock-optimization-model
   ├── State: READY
   ├── Auto-scaling: Enabled
   └── Model: main.stock_optimization.stock_optimizer@production
```

## 🔍 Troubleshooting

### "databricks command not found"
```bash
pip install databricks-cli
databricks configure --token
```

### "Bundle validation failed"
```bash
# Check databricks.yml syntax
databricks bundle validate

# View detailed errors
databricks bundle validate --verbose
```

### "Permission denied"
```sql
-- Grant required permissions
GRANT CREATE ON CATALOG main TO `your.email@company.com`;
GRANT USE CATALOG ON CATALOG main TO `your.email@company.com`;
GRANT CREATE MODEL ON SCHEMA main.stock_optimization TO `your.email@company.com`;
```

### "Job failed"
1. Go to Workflows → Jobs → [job name]
2. Click failed run
3. View logs for specific task
4. Check error messages in notebook output

### "Cluster provisioning failed"
- Check instance type availability in your region
- Try different node_type_id in databricks.yml
- Ensure your workspace has cluster creation permissions

## 🔄 Re-deployment

To update notebooks after changes:

```bash
# Validate changes
databricks bundle validate

# Deploy updates
databricks bundle deploy

# Run updated pipeline
./run-pipeline.sh
```

## 🧹 Cleanup

Remove deployed resources:

```bash
# Destroy all jobs and resources
databricks bundle destroy

# Manually delete resources if needed:
# - Feature tables: Catalog Explorer
# - Model: Catalog Explorer → Models
# - Endpoint: Serving → Endpoints
```

## 📚 Next Steps

After successful deployment:

1. **View Lineage**: Catalog Explorer → Models → Lineage tab
2. **Test Endpoint**: Run test notebook or use API
3. **Schedule Retraining**: Set up periodic job runs
4. **Monitor Performance**: Create dashboards for metrics

## 🎓 Additional Commands

```bash
# View all bundle resources
databricks bundle resources list

# Get job definition
databricks jobs get --job-id <job-id>

# Cancel running job
databricks jobs cancel-run --run-id <run-id>

# Update job configuration
databricks bundle deploy --force

# View deployment logs
databricks bundle deploy --verbose
```

## 🆘 Support

For issues:
1. Check logs in Databricks workspace
2. Review [notebooks/README.md](./README.md)
3. Check [DATABRICKS_ML_IMPLEMENTATION.md](../DATABRICKS_ML_IMPLEMENTATION.md)
4. Review Databricks documentation

---

**Deployment Type**: Serverless Databricks Jobs  
**Cluster**: Auto-provisioned (no persistent cluster needed)  
**Cost**: Pay only for job execution time  
**Recommended**: Run full pipeline first, then individual jobs as needed
