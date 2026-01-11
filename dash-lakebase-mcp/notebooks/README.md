# 📊 Stock Optimization ML Model - Databricks Implementation

This folder contains notebooks for training, registering, and deploying a classical ML model for stock optimization using **Databricks best practices** with **Feature Store** and **Unity Catalog** integration.

## 🎯 Overview

This implementation demonstrates the complete ML lifecycle for a classical optimization model on Databricks:

1. **Feature Engineering**: Create and manage features in Unity Catalog
2. **Model Training**: Train with automatic feature lookup using `FeatureLookup`
3. **Model Registration**: Register to Unity Catalog with feature metadata
4. **Model Serving**: Deploy with automatic feature retrieval from Feature Store

## 📚 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Unity Catalog                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Feature Tables                    Models                        │
│  ├── product_features         ├── stock_optimizer (v1)          │
│  │   ├── SELL_ID (PK)         │   ├── @production               │
│  │   ├── UNIT_COST            │   ├── @champion                 │
│  │   ├── SELLING_PRICE        │   └── Feature Lineage →         │
│  │   └── ...                  │                                 │
│  └── demand_features          │                                 │
│      ├── SELL_ID (PK)         │                                 │
│      ├── AVG_DAILY_DEMAND     │                                 │
│      ├── DEMAND_STD           │                                 │
│      └── ...                  │                                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Model Serving Endpoint                       │
├─────────────────────────────────────────────────────────────────┤
│  Input: {"SELL_ID": "SKU4001"}                                  │
│         ↓                                                        │
│  Automatic Feature Lookup → Product + Demand Features           │
│         ↓                                                        │
│  EOQ Optimization Model                                          │
│         ↓                                                        │
│  Output: {OPTIMAL_ORDER_QTY, SAFETY_STOCK, ...}                 │
└─────────────────────────────────────────────────────────────────┘
```

## 📖 Notebooks

### 00. Create Feature Tables
**File**: `00_create_feature_tables.py`

Creates feature tables in Unity Catalog for stock optimization:

- **Product Features**: Static attributes (costs, prices, categories, shelf space)
- **Demand Features**: Time-varying demand forecasts and volatility

**Key Concepts**:
- Feature Engineering Client for Unity Catalog
- Feature table creation with primary keys
- Realistic retail product data generation

**Run First**: This notebook must be run before training.

### 01. Train Stock Optimizer
**File**: `01_train_stock_optimizer.py`

Trains the stock optimization model using Economic Order Quantity (EOQ) with Feature Store integration:

**Key Concepts**:
- `FeatureLookup`: Define which features to use from feature tables
- `FeatureEngineeringClient.create_training_set()`: Create training set with automatic feature joining
- `fe.log_model()`: Register model with feature metadata (not `mlflow.log_model()`)
- Model signatures and input examples
- Unity Catalog model registration
- Model aliases (@production, @champion)

**Algorithm**: EOQ with safety stock optimization
- Minimizes total inventory cost (holding + ordering)
- Accounts for demand variability and lead time
- Calculates optimal reorder points and quantities

### 02. Deploy Serving Endpoint
**File**: `02_deploy_serving_endpoint.py`

Deploys the model to a serving endpoint with automatic feature lookup:

**Key Concepts**:
- Model Serving endpoint creation
- Automatic feature retrieval from Unity Catalog
- Minimal input requirements (just `SELL_ID`)
- Feature override capability for what-if analysis
- Auto-scaling configuration

### 03. Analyze Results (Optional)
**File**: `03_analyze_optimization_results.py`

Analyzes optimization results and compares scenarios:
- Financial impact analysis
- Sensitivity analysis
- Category-level insights

## 🚀 Quick Start

### Prerequisites

1. **Unity Catalog enabled** in your workspace
2. **Compute cluster** with:
   - Databricks Runtime 13.3 LTS ML or above
   - Single-user or dedicated group access mode
3. **Permissions**:
   - `CREATE MODEL` and `USE SCHEMA` on the target schema
   - `CREATE TABLE` for feature tables
   - Serving endpoint creation privileges

### Step 1: Configure

Edit the configuration in each notebook:

```python
CATALOG = "main"                    # Your Unity Catalog name
SCHEMA = "stock_optimization"       # Schema name
MODEL_NAME = "stock_optimizer"      # Model name
```

### Step 2: Run Notebooks in Order

```bash
00_create_feature_tables.py    # Create feature tables
01_train_stock_optimizer.py    # Train and register model
02_deploy_serving_endpoint.py  # Deploy to serving endpoint
```

### Step 3: Use the Model

**Batch Inference** (with automatic feature lookup):

```python
import mlflow
mlflow.set_registry_uri("databricks-uc")

# Load model
model = mlflow.pyfunc.load_model("models:/main.stock_optimization.stock_optimizer@production")

# Predict - only need SELL_IDs!
input_df = pd.DataFrame([
    {'SELL_ID': 'SKU4001', 'PRODUCT_NAME': 'Stone & Wood Pacific Ale 6pk'},
    {'SELL_ID': 'SKU4002', 'PRODUCT_NAME': 'Balter XPA 4pk'},
])

results = model.predict(input_df)  # Features fetched automatically!
```

**Real-time Inference** (via serving endpoint):

```python
import requests

response = requests.post(
    f"{workspace_url}/serving-endpoints/stock-optimization-model/invocations",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"dataframe_records": [
        {'SELL_ID': 'SKU4001', 'PRODUCT_NAME': 'Stone & Wood Pacific Ale 6pk'}
    ]}
)

results = response.json()
```

## 🔑 Key Features

### 1. Feature Store Integration

**Automatic Feature Lookup**: Models registered with `fe.log_model()` automatically retrieve features during inference:

```python
# Training
training_set = fe.create_training_set(
    df=base_df,
    feature_lookups=[
        FeatureLookup(table_name="product_features", feature_names=[...], lookup_key="SELL_ID"),
        FeatureLookup(table_name="demand_features", feature_names=[...], lookup_key="SELL_ID"),
    ]
)

# Register with feature metadata
fe.log_model(
    model=model,
    training_set=training_set,  # Links model to features
    registered_model_name="main.stock_optimization.stock_optimizer"
)
```

### 2. Unity Catalog Governance

**Complete Lineage**: View feature-to-model lineage in Catalog Explorer
- Tracks which features were used to train each model version
- Shows feature table versions and dependencies
- Enables impact analysis for feature changes

**Access Control**: Unified governance across features and models
- Control who can read features
- Control who can use models
- Audit all access

### 3. Classical ML Best Practices

Following Databricks documentation patterns:

- ✅ Model signatures with input examples
- ✅ MLflow pyfunc wrapper for consistency
- ✅ Parameter and metric logging
- ✅ Model aliases for deployment stages
- ✅ Feature Engineering client (not legacy FeatureStoreClient)
- ✅ Unity Catalog (not workspace registry)

## 📊 Model Details

### Economic Order Quantity (EOQ) Model

**Formula**:
```
EOQ = √((2 × D × S) / (H × C))
```

Where:
- **D** = Annual demand
- **S** = Ordering cost per order
- **H** = Holding cost rate
- **C** = Unit cost per item

**Safety Stock**:
```
Safety Stock = Z × σ × √L
```

Where:
- **Z** = Service level factor (z-score)
- **σ** = Demand standard deviation
- **L** = Lead time in days

**Reorder Point**:
```
ROP = (Average Daily Demand × Lead Time) + Safety Stock
```

### Model Inputs (from Feature Store)

From **Product Features**:
- `UNIT_COST`: Cost per unit
- `SELLING_PRICE`: Selling price per unit
- `CATEGORY_NAME`: Product category
- `SUBCATEGORY_NAME`: Product subcategory
- `SHELF_SPACE_CM`: Shelf space allocation

From **Demand Features**:
- `AVG_DAILY_DEMAND`: Average daily demand forecast
- `DEMAND_STD`: Demand standard deviation (volatility)
- `TOTAL_FORECAST_30D`: 30-day total forecast

### Model Outputs

- `OPTIMAL_ORDER_QTY`: Recommended order quantity
- `SAFETY_STOCK`: Safety stock level
- `REORDER_POINT`: When to reorder
- `MAX_STOCK_LEVEL`: Maximum inventory level
- `ANNUAL_HOLDING_COST`: Annual holding cost
- `ANNUAL_ORDERING_COST`: Annual ordering cost
- `TOTAL_ANNUAL_COST`: Total annual cost
- `EXPECTED_ANNUAL_REVENUE`: Expected revenue
- `EXPECTED_ANNUAL_PROFIT`: Expected profit
- `TURNOVER_RATE`: Inventory turnover rate

## 🔄 Feature Updates

In production, update features regularly:

```python
from databricks.feature_engineering import FeatureEngineeringClient
fe = FeatureEngineeringClient()

# Update demand forecasts daily
fe.write_table(
    name="main.stock_optimization.demand_features",
    df=new_demand_forecasts_df,
    mode='merge'
)

# Models automatically use updated features!
```

## 🎓 Learning Resources

### Databricks Documentation
- [End-to-end Classic ML on Databricks](https://docs.databricks.com/mlflow/end-to-end-example.html)
- [Feature Store with Unity Catalog](https://docs.databricks.com/machine-learning/feature-store/train-models-with-feature-store.html)
- [Models in Unity Catalog](https://docs.databricks.com/machine-learning/manage-model-lifecycle/)
- [Model Serving](https://docs.databricks.com/machine-learning/model-serving/)

### Key Concepts
- **FeatureLookup**: Defines features to retrieve from feature tables
- **TrainingSet**: Dataset with automatically joined features
- **fe.log_model()**: Registers model with feature metadata
- **Automatic Feature Lookup**: Model fetches features during inference
- **Model Aliases**: Manage deployment stages (@production, @champion)

## 🛠️ Troubleshooting

### "Model signature required"
**Solution**: Use `input_example` parameter or define signature explicitly:
```python
signature = infer_signature(training_df, predictions)
```

### "Features not found during inference"
**Solution**: Ensure features exist in feature tables and SELL_ID matches:
```python
spark.sql(f"SELECT * FROM {PRODUCT_FEATURES_TABLE} WHERE SELL_ID = 'SKU4001'")
```

### "Permission denied"
**Solution**: Grant required privileges:
```sql
GRANT USE CATALOG ON CATALOG main TO `user@company.com`;
GRANT USE SCHEMA ON SCHEMA main.stock_optimization TO `user@company.com`;
GRANT CREATE MODEL ON SCHEMA main.stock_optimization TO `user@company.com`;
GRANT SELECT ON TABLE main.stock_optimization.product_features TO `user@company.com`;
```

## 📈 Next Steps

1. **Monitor Model Performance**: Set up monitoring dashboards
2. **A/B Testing**: Compare different optimization strategies
3. **Feature Engineering**: Add more sophisticated demand forecasts
4. **Model Improvements**: Incorporate seasonality, promotions, constraints
5. **Integration**: Connect to inventory management systems

## 🤝 Contributing

When adding new features or models:
1. Follow the established patterns in these notebooks
2. Use `fe.log_model()` for Feature Store integration
3. Register all models to Unity Catalog
4. Document feature dependencies
5. Add comprehensive tests

## 📄 License

This example code is provided for educational purposes.
