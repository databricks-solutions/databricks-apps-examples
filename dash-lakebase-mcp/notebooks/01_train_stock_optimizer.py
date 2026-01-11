# Databricks notebook source
# MAGIC %md
# MAGIC # 🏪 Stock Optimization Model - Training with Feature Store
# MAGIC 
# MAGIC This notebook trains and registers a **Stock Optimization** model to **Unity Catalog** using **Feature Store** integration.
# MAGIC 
# MAGIC The model uses **Economic Order Quantity (EOQ)** calculations with safety stock to optimize inventory levels.
# MAGIC 
# MAGIC ## What You'll Learn
# MAGIC - Create training sets with FeatureLookup from Unity Catalog
# MAGIC - Train classical ML models with Feature Store integration
# MAGIC - Register models to Unity Catalog with feature metadata
# MAGIC - Set model aliases for deployment
# MAGIC - Track feature lineage automatically
# MAGIC 
# MAGIC ## Prerequisites
# MAGIC - Run `00_create_feature_tables` notebook first to create feature tables

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
CATALOG = "main"                    # Your Unity Catalog name
SCHEMA = "stock_optimization"       # Schema for features and models
MODEL_NAME = "stock_optimizer"      # Model name

# Feature tables (created in notebook 00)
PRODUCT_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.product_features"
DEMAND_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.demand_features"

# Full UC path
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

print(f"📊 Product Features: {PRODUCT_FEATURES_TABLE}")
print(f"📈 Demand Features: {DEMAND_FEATURES_TABLE}")
print(f"📦 Model will be registered to: {UC_MODEL_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Install Dependencies

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering numpy pandas mlflow -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 Setup MLflow & Feature Engineering

# COMMAND ----------

# DBTITLE 1,Import Libraries
import mlflow
import mlflow.pyfunc
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional
import json
import os
import tempfile
from mlflow.models.signature import infer_signature
from mlflow import MlflowClient
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup

# Configure MLflow for Unity Catalog
mlflow.set_registry_uri("databricks-uc")

# Initialize Feature Engineering Client
fe = FeatureEngineeringClient()

print("✅ MLflow configured for Unity Catalog")
print("✅ Feature Engineering Client initialized")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⚙️ Model Configuration
# MAGIC 
# MAGIC These parameters control the EOQ optimization algorithm:

# COMMAND ----------

# DBTITLE 1,Optimization Parameters
@dataclass
class OptimizationConfig:
    """Configuration for stock optimization algorithm"""
    holding_cost_rate: float = 0.25    # 25% annual holding cost
    ordering_cost: float = 50.0        # $50 per order
    lead_time_days: int = 7            # 7 days to restock
    service_level: float = 0.95        # 95% service level target
    safety_factor: float = 1.65        # Z-score for 95% confidence
    max_storage_capacity: int = 10000  # Max units storable

config = OptimizationConfig()

print("⚙️ Optimization Parameters:")
print(f"   • Holding Cost Rate: {config.holding_cost_rate*100}%/year")
print(f"   • Ordering Cost: ${config.ordering_cost} per order")
print(f"   • Lead Time: {config.lead_time_days} days")
print(f"   • Service Level: {config.service_level*100}%")
print(f"   • Safety Factor (Z): {config.safety_factor}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧠 Model Implementation
# MAGIC 
# MAGIC The `StockOptimizerModel` implements the EOQ formula:
# MAGIC 
# MAGIC $$EOQ = \sqrt{\frac{2 \times D \times S}{H \times C}}$$
# MAGIC 
# MAGIC Where:
# MAGIC - **D** = Annual demand
# MAGIC - **S** = Ordering cost per order
# MAGIC - **H** = Holding cost rate
# MAGIC - **C** = Unit cost

# COMMAND ----------

# DBTITLE 1,Stock Optimizer Model Class
class StockOptimizerModel(mlflow.pyfunc.PythonModel):
    """
    MLflow pyfunc model for stock optimization using EOQ.
    
    This model integrates with Feature Store to automatically retrieve
    product and demand features during training and inference.
    
    Input: DataFrame with SELL_ID (and optionally feature values)
    Output: DataFrame with optimization results including OPTIMAL_ORDER_QTY, SAFETY_STOCK, etc.
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
    
    def load_context(self, context):
        """Load config from artifacts"""
        config_path = context.artifacts.get("config")
        if config_path:
            with open(config_path, "r") as f:
                self.config = OptimizationConfig(**json.load(f))
        else:
            self.config = OptimizationConfig()
    
    def calculate_eoq(self, annual_demand, ordering_cost, unit_cost, holding_cost_rate):
        """Economic Order Quantity formula"""
        if annual_demand <= 0 or unit_cost <= 0:
            return 0.0
        return np.sqrt((2 * annual_demand * ordering_cost) / (holding_cost_rate * unit_cost))
    
    def calculate_safety_stock(self, demand_std, lead_time_days, safety_factor):
        """Safety stock = Z × σ × √L"""
        if demand_std <= 0:
            return 0.0
        return safety_factor * demand_std * np.sqrt(lead_time_days)
    
    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        """
        Run optimization on input products.
        
        Expected input columns (automatically joined from Feature Store if using fe.log_model):
        - SELL_ID: Product identifier (required - primary key)
        - AVG_DAILY_DEMAND: Average daily demand (from feature store)
        - DEMAND_STD: Standard deviation of demand (from feature store)
        - UNIT_COST: Cost per unit (from feature store)
        - SELLING_PRICE: Selling price per unit (from feature store)
        """
        results = []
        
        for _, row in model_input.iterrows():
            sell_id = row.get('SELL_ID', 'UNKNOWN')
            product_name = row.get('PRODUCT_NAME', 'Unknown')
            avg_daily_demand = float(row.get('AVG_DAILY_DEMAND', 0))
            demand_std = float(row.get('DEMAND_STD', avg_daily_demand * 0.2))
            unit_cost = float(row.get('UNIT_COST', 10.0))
            selling_price = float(row.get('SELLING_PRICE', unit_cost * 2))
            
            annual_demand = avg_daily_demand * 365
            
            # EOQ calculation
            eoq = self.calculate_eoq(
                annual_demand, self.config.ordering_cost,
                unit_cost, self.config.holding_cost_rate
            )
            
            # Safety stock
            safety_stock = self.calculate_safety_stock(
                demand_std, self.config.lead_time_days, self.config.safety_factor
            )
            
            # Reorder point
            reorder_point = (avg_daily_demand * self.config.lead_time_days) + safety_stock
            
            # Apply capacity limit
            optimal_order_qty = min(eoq, self.config.max_storage_capacity)
            max_stock_level = optimal_order_qty + safety_stock
            
            # Cost calculations
            avg_inventory = optimal_order_qty / 2 + safety_stock
            annual_holding_cost = avg_inventory * unit_cost * self.config.holding_cost_rate
            annual_ordering_cost = (annual_demand / optimal_order_qty) * self.config.ordering_cost if optimal_order_qty > 0 else 0
            total_annual_cost = annual_holding_cost + annual_ordering_cost
            
            # Profit calculations
            expected_revenue = annual_demand * selling_price
            expected_profit = expected_revenue - (annual_demand * unit_cost) - total_annual_cost
            turnover_rate = annual_demand / max_stock_level if max_stock_level > 0 else 0
            
            results.append({
                'SELL_ID': sell_id,
                'PRODUCT_NAME': product_name,
                'AVG_DAILY_DEMAND': round(avg_daily_demand, 2),
                'OPTIMAL_ORDER_QTY': round(optimal_order_qty, 0),
                'SAFETY_STOCK': round(safety_stock, 0),
                'REORDER_POINT': round(reorder_point, 0),
                'MAX_STOCK_LEVEL': round(max_stock_level, 0),
                'ANNUAL_HOLDING_COST': round(annual_holding_cost, 2),
                'ANNUAL_ORDERING_COST': round(annual_ordering_cost, 2),
                'TOTAL_ANNUAL_COST': round(total_annual_cost, 2),
                'EXPECTED_ANNUAL_REVENUE': round(expected_revenue, 2),
                'EXPECTED_ANNUAL_PROFIT': round(expected_profit, 2),
                'TURNOVER_RATE': round(turnover_rate, 2),
                'SERVICE_LEVEL': self.config.service_level,
            })
        
        return pd.DataFrame(results)

print("✅ Model class defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Create Training Set with Feature Lookups
# MAGIC 
# MAGIC We use **FeatureLookup** to automatically join features from Unity Catalog:

# COMMAND ----------

# DBTITLE 1,Load Base Training DataFrame
# Create base DataFrame with product IDs and labels
# In production, this would come from historical sales/inventory data
base_training_df = spark.sql(f"""
    SELECT DISTINCT
        d.SELL_ID,
        p.PRODUCT_NAME,
        p.CATEGORY_NAME
    FROM {DEMAND_FEATURES_TABLE} d
    INNER JOIN {PRODUCT_FEATURES_TABLE} p ON d.SELL_ID = p.SELL_ID
""")

print(f"📊 Base training DataFrame: {base_training_df.count()} products")
display(base_training_df)

# COMMAND ----------

# DBTITLE 1,Define Feature Lookups
# Define which features to use from each feature table
feature_lookups = [
    # Product features: costs, pricing, and attributes
    FeatureLookup(
        table_name=PRODUCT_FEATURES_TABLE,
        feature_names=['UNIT_COST', 'SELLING_PRICE', 'CATEGORY_NAME', 'SUBCATEGORY_NAME', 'SHELF_SPACE_CM'],
        lookup_key='SELL_ID',
    ),
    # Demand features: forecasts and volatility
    FeatureLookup(
        table_name=DEMAND_FEATURES_TABLE,
        feature_names=['AVG_DAILY_DEMAND', 'DEMAND_STD', 'TOTAL_FORECAST_30D'],
        lookup_key='SELL_ID',
    )
]

print("✅ Defined feature lookups:")
print(f"   • {PRODUCT_FEATURES_TABLE}: 5 features")
print(f"   • {DEMAND_FEATURES_TABLE}: 3 features")

# COMMAND ----------

# DBTITLE 1,Create Training Set
# Create training set with automatic feature joining
training_set = fe.create_training_set(
    df=base_training_df,
    feature_lookups=feature_lookups,
    label=None,  # Unsupervised optimization (no target label)
    exclude_columns=['CATEGORY_NAME']  # Exclude as it's not needed for model
)

# Load the training data
training_df = training_set.load_df().toPandas()

print(f"✅ Training set created: {len(training_df)} rows")
print(f"   Columns: {list(training_df.columns)}")
display(training_df.head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Train Model & Infer Signature

# COMMAND ----------

# DBTITLE 1,Train and Get Signature
model = StockOptimizerModel(config=config)

# Run inference to get output for signature
print("→ Running model inference for signature...")
sample_output = model.predict(None, training_df)

# Infer signature
signature = infer_signature(training_df, sample_output)
print("✅ Model signature inferred")
print(f"   Input features: {len(training_df.columns)}")
print(f"   Output features: {len(sample_output.columns)}")

# Show sample results
print("\n📤 Sample Optimization Results:")
display(sample_output[['SELL_ID', 'PRODUCT_NAME', 'OPTIMAL_ORDER_QTY', 'SAFETY_STOCK', 'REORDER_POINT', 'EXPECTED_ANNUAL_PROFIT']].head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗄️ Create Unity Catalog Schema

# COMMAND ----------

# DBTITLE 1,Setup Catalog & Schema
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ Created {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Register Model to Unity Catalog with Feature Store
# MAGIC 
# MAGIC Using `fe.log_model()` instead of `mlflow.log_model()` to capture feature metadata:

# COMMAND ----------

# DBTITLE 1,Setup Experiment
user = spark.conf.get('spark.databricks.workspace.user', 'unknown')
experiment_name = f"/Users/{user}/stock_optimization_feature_store"
mlflow.set_experiment(experiment_name)
print(f"📊 Experiment: {experiment_name}")

# COMMAND ----------

# DBTITLE 1,Log Model with Feature Store Integration
with tempfile.TemporaryDirectory() as tmpdir:
    # Save config artifact
    config_path = os.path.join(tmpdir, "config.json")
    with open(config_path, "w") as f:
        json.dump(asdict(config), f, indent=2)
    
    with mlflow.start_run(run_name="stock_optimizer_with_features") as run:
        run_id = run.info.run_id
        print(f"🏃 Run ID: {run_id}")
        
        # Log parameters
        mlflow.log_params({
            "holding_cost_rate": config.holding_cost_rate,
            "ordering_cost": config.ordering_cost,
            "lead_time_days": config.lead_time_days,
            "service_level": config.service_level,
            "safety_factor": config.safety_factor,
            "num_products": len(training_df),
        })
        
        # Log metrics
        mlflow.log_metrics({
            "total_products": len(sample_output),
            "avg_optimal_order_qty": sample_output['OPTIMAL_ORDER_QTY'].mean(),
            "total_annual_cost": sample_output['TOTAL_ANNUAL_COST'].sum(),
            "total_annual_profit": sample_output['EXPECTED_ANNUAL_PROFIT'].sum(),
            "avg_turnover_rate": sample_output['TURNOVER_RATE'].mean(),
        })
        
        # Log metrics by category  
        category_products = spark.table(PRODUCT_FEATURES_TABLE).select('SELL_ID', 'CATEGORY_NAME').toPandas()
        sample_with_cat = sample_output.merge(category_products, on='SELL_ID', how='left')
        
        for category in sample_with_cat['CATEGORY_NAME'].dropna().unique():
            cat_data = sample_with_cat[sample_with_cat['CATEGORY_NAME'] == category]
            cat_key = category.lower().replace(' ', '_').replace('&', 'and')
            mlflow.log_metric(f"{cat_key}_total_cost", cat_data['TOTAL_ANNUAL_COST'].sum())
            mlflow.log_metric(f"{cat_key}_total_profit", cat_data['EXPECTED_ANNUAL_PROFIT'].sum())
        
        # ⭐ KEY: Use fe.log_model() instead of mlflow.log_model()
        # This captures the feature store metadata for automatic feature lookup
        print("📤 Registering model to Unity Catalog with Feature Store metadata...")
        model_info = fe.log_model(
            model=StockOptimizerModel(config=config),
            artifact_path="stock_optimizer",
            flavor=mlflow.pyfunc,
            training_set=training_set,  # ⭐ This links the model to features
            signature=signature,
            input_example=training_df.head(3),
            pip_requirements=["numpy", "pandas"],
            registered_model_name=UC_MODEL_PATH,
        )
        
        print(f"✅ Model registered: {UC_MODEL_PATH}")
        print(f"   Features will be automatically looked up during inference!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🏷️ Set Model Aliases

# COMMAND ----------

# DBTITLE 1,Set Production Alias
client = MlflowClient()

versions = client.search_model_versions(f"name='{UC_MODEL_PATH}'")
if versions:
    latest_version = max([int(v.version) for v in versions])
    
    # Set aliases
    client.set_registered_model_alias(UC_MODEL_PATH, "production", latest_version)
    client.set_registered_model_alias(UC_MODEL_PATH, "champion", latest_version)
    
    print(f"🏷️ Aliases set for version {latest_version}:")
    print(f"   • @production")
    print(f"   • @champion")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Test Model with Automatic Feature Lookup

# COMMAND ----------

# DBTITLE 1,Test Batch Inference with Feature Store
# Load model from Unity Catalog
loaded_model = mlflow.pyfunc.load_model(f"models:/{UC_MODEL_PATH}@production")

# Test with just SELL_IDs - features will be automatically retrieved!
test_data = training_df[['SELL_ID', 'PRODUCT_NAME']].head(5)

print("📥 Test Input (only SELL_IDs):")
display(test_data)

# Model will automatically fetch features from Feature Store
predictions = loaded_model.predict(training_df.head(5))

print("\n📤 Optimization Results (with auto-fetched features):")
display(predictions[['SELL_ID', 'PRODUCT_NAME', 'OPTIMAL_ORDER_QTY', 'SAFETY_STOCK', 'REORDER_POINT', 'EXPECTED_ANNUAL_PROFIT']])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Results Summary

# COMMAND ----------

# DBTITLE 1,Financial Summary
print("="*60)
print("💰 OPTIMIZATION RESULTS")
print("="*60)
print(f"\n📊 Financial Overview:")
print(f"   Total Annual Cost:    ${sample_output['TOTAL_ANNUAL_COST'].sum():>12,.2f}")
print(f"   Total Annual Revenue: ${sample_output['EXPECTED_ANNUAL_REVENUE'].sum():>12,.2f}")
print(f"   Total Annual Profit:  ${sample_output['EXPECTED_ANNUAL_PROFIT'].sum():>12,.2f}")
print(f"\n📦 Inventory Overview:")
print(f"   Total Optimal Stock:  {sample_output['OPTIMAL_ORDER_QTY'].sum():>12,.0f} units")
print(f"   Total Safety Stock:   {sample_output['SAFETY_STOCK'].sum():>12,.0f} units")
print(f"   Avg Turnover Rate:    {sample_output['TURNOVER_RATE'].mean():>12.1f}x")

# By category
print(f"\n📁 Results by Category:")
for category in sample_with_cat['CATEGORY_NAME'].dropna().unique():
    cat_data = sample_with_cat[sample_with_cat['CATEGORY_NAME'] == category]
    print(f"\n   {category}:")
    print(f"      Products: {len(cat_data)}")
    print(f"      Total Stock: {cat_data['OPTIMAL_ORDER_QTY'].sum():,.0f} units")
    print(f"      Annual Cost: ${cat_data['TOTAL_ANNUAL_COST'].sum():,.2f}")
    print(f"      Annual Profit: ${cat_data['EXPECTED_ANNUAL_PROFIT'].sum():,.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Complete!
# MAGIC 
# MAGIC **Model successfully registered to Unity Catalog with Feature Store integration!**
# MAGIC 
# MAGIC | Property | Value |
# MAGIC |----------|-------|
# MAGIC | Model Path | `{UC_MODEL_PATH}` |
# MAGIC | Aliases | `@production`, `@champion` |
# MAGIC | Product Features | `{PRODUCT_FEATURES_TABLE}` |
# MAGIC | Demand Features | `{DEMAND_FEATURES_TABLE}` |
# MAGIC 
# MAGIC ### ✨ Key Benefits
# MAGIC 
# MAGIC 1. **Automatic Feature Lookup**: Model automatically retrieves features during inference
# MAGIC 2. **Feature Lineage**: View complete lineage in Catalog Explorer
# MAGIC 3. **Feature Governance**: Unity Catalog controls feature access
# MAGIC 4. **Consistent Features**: Training and inference use identical feature definitions
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Deploy Serving Endpoint**: Run `02_deploy_serving_endpoint` notebook
# MAGIC 2. **View Lineage**: Open Catalog Explorer → Models → `{UC_MODEL_PATH}` → Lineage tab
# MAGIC 3. **Use in Production**:
# MAGIC 
# MAGIC ```python
# MAGIC # Load model
# MAGIC import mlflow
# MAGIC mlflow.set_registry_uri("databricks-uc")
# MAGIC model = mlflow.pyfunc.load_model(f"models:/{UC_MODEL_PATH}@production")
# MAGIC 
# MAGIC # Predict - features fetched automatically!
# MAGIC results = model.predict(input_df[['SELL_ID', 'PRODUCT_NAME']])
# MAGIC ```
# MAGIC 
# MAGIC ### Updating Features
# MAGIC 
# MAGIC When demand forecasts change, update the feature table:
# MAGIC 
# MAGIC ```python
# MAGIC from databricks.feature_engineering import FeatureEngineeringClient
# MAGIC fe = FeatureEngineeringClient()
# MAGIC 
# MAGIC # Update demand features
# MAGIC fe.write_table(
# MAGIC     name="{DEMAND_FEATURES_TABLE}",
# MAGIC     df=new_forecasts_df,
# MAGIC     mode='merge'
# MAGIC )
# MAGIC 
# MAGIC # Model will automatically use updated features!
# MAGIC ```
