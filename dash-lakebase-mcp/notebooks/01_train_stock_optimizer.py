# Databricks notebook source
# MAGIC %md
# MAGIC # 🏪 Range Optimizer Model - Training with Feature Store
# MAGIC
# MAGIC This notebook trains and registers a **Range Optimizer** model to **Unity Catalog** using **Feature Store** integration.
# MAGIC
# MAGIC ## Schema Alignment
# MAGIC This model is **aligned** with the MCP app's schema:
# MAGIC - Primary Key: `SKU_ID` (e.g., "SKU3001")
# MAGIC - Input: `SKU_ID`, `SKU_NAME`, `WEEKLY_UNITS`, `DEMAND_STD`, `UNIT_COST`, `UNIT_PRICE`
# MAGIC - Output: Optimization results including facings recommendations
# MAGIC
# MAGIC ## What You'll Learn
# MAGIC - Create training sets with FeatureLookup from Unity Catalog
# MAGIC - Train classical ML models with Feature Store integration
# MAGIC - Register models to Unity Catalog with feature metadata
# MAGIC - Set model aliases for deployment
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - Run `00_create_feature_tables` notebook first to create feature tables

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Install Dependencies
# MAGIC
# MAGIC **Note:** This must run BEFORE any variable initialization to avoid losing state after `restartPython()`.

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering numpy pandas mlflow -q

# COMMAND ----------

# MAGIC %md
# MAGIC Restart Python to pick up installed packages:

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
# Define widgets for job parameters (works when running interactively or as a job)
dbutils.widgets.text("catalog", "smarter_forecasting", "Catalog Name")
dbutils.widgets.text("schema", "stock_optimization", "Schema Name")
dbutils.widgets.text("catalog_storage_location", 
                     "abfss://iceberg@stdavidokeeffeinterop02.dfs.core.windows.net/root/catalogs/smarter_forecasting",
                     "Catalog Storage Location")
dbutils.widgets.text("user", "david.okeeffe@databricks.com"
                     "abfss://iceberg@stdavidokeeffeinterop02.dfs.core.windows.net/root/catalogs/smarter_forecasting",
                     "Catalog Storage Location")

# Get parameter values
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
CATALOG_STORAGE_LOCATION = dbutils.widgets.get("catalog_storage_location")
MODEL_NAME = "range_optimizer"      # Model name

# Feature tables (created in notebook 00)
SKU_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.sku_features"
DEMAND_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.demand_features"

# Full UC path
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

print(f"📊 SKU Features: {SKU_FEATURES_TABLE}")
print(f"📈 Demand Features: {DEMAND_FEATURES_TABLE}")
print(f"📦 Model will be registered to: {UC_MODEL_PATH}")
print(f"📁 Catalog Storage: {CATALOG_STORAGE_LOCATION}")

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
# MAGIC These parameters control the range optimization algorithm:

# COMMAND ----------

# DBTITLE 1,Optimization Parameters
@dataclass
class OptimizationConfig:
    """Configuration for range optimization algorithm"""
    min_facings: int = 1              # Minimum facings per SKU
    max_facings: int = 6              # Maximum facings per SKU
    target_service_level: float = 0.95  # 95% service level target
    safety_factor: float = 1.65       # Z-score for 95% confidence
    weekly_to_annual: float = 52.0    # Convert weekly to annual
    holding_cost_rate: float = 0.25   # 25% annual holding cost
    ordering_cost: float = 50.0       # $50 per order
    lead_time_days: int = 7           # 7 days to restock

config = OptimizationConfig()

print("⚙️ Optimization Parameters:")
print(f"   • Min Facings: {config.min_facings}")
print(f"   • Max Facings: {config.max_facings}")
print(f"   • Service Level: {config.target_service_level*100}%")
print(f"   • Safety Factor (Z): {config.safety_factor}")
print(f"   • Lead Time: {config.lead_time_days} days")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧠 Model Implementation
# MAGIC
# MAGIC The `RangeOptimizerModel` calculates optimal facings based on:
# MAGIC - Weekly demand and volatility
# MAGIC - Margin contribution per facing
# MAGIC - Safety stock requirements

# COMMAND ----------

# DBTITLE 1,Range Optimizer Model Class
class RangeOptimizerModel(mlflow.pyfunc.PythonModel):
    """
    MLflow pyfunc model for range optimization.
    
    Aligned with MCP app schema:
    - Input: DataFrame with SKU_ID (features auto-fetched from Feature Store)
    - Output: DataFrame with optimization results
    
    Expected input columns (from Feature Store):
    - SKU_ID: Product identifier (required - primary key)
    - SKU_NAME: Product name
    - WEEKLY_UNITS: Average weekly demand
    - DEMAND_STD: Standard deviation of demand
    - UNIT_COST: Cost per unit
    - UNIT_PRICE: Selling price per unit
    - CATEGORY: Product category
    - SEGMENT: Product segment
    - BRAND: Brand name
    - PACK_WIDTH_MM: Shelf space width
    - IS_MUST_STOCK: Whether item must be stocked
    - IS_PRIVATE_LABEL: Whether item is private label
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
    
    def calculate_optimal_facings(self, weekly_units, demand_std, margin, is_must_stock):
        """
        Calculate optimal facings based on demand and profitability.
        
        Uses a simplified space productivity formula:
        - Higher weekly profit → more facings
        - Higher volatility → more safety stock → more facings
        """
        if weekly_units <= 0 or margin <= 0:
            return self.config.min_facings if is_must_stock else 0
        
        # Weekly profit per unit
        weekly_profit = weekly_units * margin
        
        # Safety stock multiplier
        safety_multiplier = 1 + (demand_std / weekly_units) if weekly_units > 0 else 1
        
        # Space productivity score (profit per unit, adjusted for volatility)
        productivity_score = weekly_profit / safety_multiplier
        
        # Convert productivity to facings recommendation
        if productivity_score > 200:
            recommended = 5
        elif productivity_score > 100:
            recommended = 4
        elif productivity_score > 50:
            recommended = 3
        elif productivity_score > 25:
            recommended = 2
        else:
            recommended = 1 if is_must_stock else 0
        
        # Apply constraints
        return max(
            self.config.min_facings if is_must_stock else 0,
            min(recommended, self.config.max_facings)
        )
    
    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        """
        Run optimization on input SKUs.
        
        Returns optimization results aligned with MCP app opt_recommended_planogram schema.
        """
        results = []
        
        for _, row in model_input.iterrows():
            # Extract values (handle both uppercase and lowercase)
            sku_id = row.get('SKU_ID') or row.get('sku_id', 'UNKNOWN')
            sku_name = row.get('SKU_NAME') or row.get('sku_name', 'Unknown')
            category = row.get('CATEGORY') or row.get('category', 'Unknown')
            segment = row.get('SEGMENT') or row.get('segment', 'Unknown')
            brand = row.get('BRAND') or row.get('brand', 'Unknown')
            
            weekly_units = float(row.get('WEEKLY_UNITS') or row.get('weekly_units', 50))
            demand_std = float(row.get('DEMAND_STD') or row.get('demand_std', weekly_units * 0.2))
            unit_cost = float(row.get('UNIT_COST') or row.get('unit_cost', 10.0))
            unit_price = float(row.get('UNIT_PRICE') or row.get('unit_price', unit_cost * 1.5))
            pack_width = int(row.get('PACK_WIDTH_MM') or row.get('pack_width_mm', 100))
            is_must_stock = bool(row.get('IS_MUST_STOCK') or row.get('is_must_stock', False))
            is_private_label = bool(row.get('IS_PRIVATE_LABEL') or row.get('is_private_label', False))
            current_facings = int(row.get('CURRENT_FACINGS') or row.get('current_facings', 2))
            
            # Calculate margin
            margin = unit_price - unit_cost
            
            # Calculate optimal facings
            recommended_facings = self.calculate_optimal_facings(
                weekly_units, demand_std, margin, is_must_stock
            )
            
            # Calculate facings change
            facings_change = recommended_facings - current_facings
            
            # Determine change type
            if current_facings == 0 and recommended_facings > 0:
                change_type = "new"
            elif recommended_facings == 0 and current_facings > 0:
                change_type = "removed"
            elif facings_change > 0:
                change_type = "increased"
            elif facings_change < 0:
                change_type = "decreased"
            else:
                change_type = "no_change"
            
            # Calculate expected metrics
            expected_weekly_profit = weekly_units * margin
            space_productivity = expected_weekly_profit / max(recommended_facings, 1)
            is_ranged = recommended_facings > 0
            
            results.append({
                'SKU_ID': sku_id,
                'SKU_NAME': sku_name,
                'CATEGORY': category,
                'SEGMENT': segment,
                'BRAND': brand,
                'WEEKLY_UNITS': round(weekly_units, 2),
                'UNIT_COST': round(unit_cost, 2),
                'UNIT_PRICE': round(unit_price, 2),
                'MARGIN': round(margin, 2),
                'PACK_WIDTH_MM': pack_width,
                'IS_MUST_STOCK': is_must_stock,
                'IS_PRIVATE_LABEL': is_private_label,
                'CURRENT_FACINGS': current_facings,
                'RECOMMENDED_FACINGS': recommended_facings,
                'FACINGS_CHANGE': facings_change,
                'CHANGE_TYPE': change_type,
                'IS_RANGED': is_ranged,
                'EXPECTED_WEEKLY_UNITS': round(weekly_units, 0),
                'EXPECTED_WEEKLY_PROFIT': round(expected_weekly_profit, 2),
                'SPACE_PRODUCTIVITY': round(space_productivity, 2),
                'SERVICE_LEVEL': self.config.target_service_level,
            })
        
        return pd.DataFrame(results)

print("✅ Model class defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Create Training Set with Feature Lookups

# COMMAND ----------

# DBTITLE 1,Load Base Training DataFrame
# Create base DataFrame with SKU IDs (CATEGORY will come from FeatureLookup)
base_training_df = spark.sql(f"""
    SELECT DISTINCT
        d.SKU_ID,
        p.SKU_NAME
    FROM {DEMAND_FEATURES_TABLE} d
    INNER JOIN {SKU_FEATURES_TABLE} p ON d.SKU_ID = p.SKU_ID
""")

print(f"📊 Base training DataFrame: {base_training_df.count()} SKUs")
display(base_training_df)

# COMMAND ----------

# DBTITLE 1,Define Feature Lookups
# Define which features to use from each feature table
feature_lookups = [
    # SKU features: costs, pricing, and attributes
    FeatureLookup(
        table_name=SKU_FEATURES_TABLE,
        feature_names=['UNIT_COST', 'UNIT_PRICE', 'CATEGORY', 'SEGMENT', 'BRAND', 'PACK_WIDTH_MM', 'IS_MUST_STOCK', 'IS_PRIVATE_LABEL'],
        lookup_key='SKU_ID',
    ),
    # Demand features: forecasts and volatility
    FeatureLookup(
        table_name=DEMAND_FEATURES_TABLE,
        feature_names=['WEEKLY_UNITS', 'DEMAND_STD', 'FORECAST_4W'],
        lookup_key='SKU_ID',
    )
]

print("✅ Defined feature lookups:")
print(f"   • {SKU_FEATURES_TABLE}: 8 features")
print(f"   • {DEMAND_FEATURES_TABLE}: 3 features")

# COMMAND ----------

# DBTITLE 1,Create Training Set
# Create training set with automatic feature joining
training_set = fe.create_training_set(
    df=base_training_df,
    feature_lookups=feature_lookups,
    label=None,  # Unsupervised optimization (no target label)
)

# Load the training data
training_df = training_set.load_df().toPandas()

# Add default CURRENT_FACINGS for training (model will use this as baseline)
training_df['CURRENT_FACINGS'] = 2

print(f"✅ Training set created: {len(training_df)} rows")
print(f"   Columns: {list(training_df.columns)}")
display(training_df.head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Train Model & Infer Signature

# COMMAND ----------

# DBTITLE 1,Train and Get Signature
model = RangeOptimizerModel(config=config)

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
display(sample_output[['SKU_ID', 'SKU_NAME', 'RECOMMENDED_FACINGS', 'FACINGS_CHANGE', 'CHANGE_TYPE', 'EXPECTED_WEEKLY_PROFIT']].head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗄️ Create Unity Catalog Schema

# COMMAND ----------

# DBTITLE 1,Setup Catalog & Schema
# Create catalog with managed location (required when metastore has no root storage credential)
try:
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} MANAGED LOCATION '{CATALOG_STORAGE_LOCATION}'")
    print(f"✅ Created catalog {CATALOG} with managed location")
except Exception as e:
    if "already exists" in str(e).lower() or "CATALOG_ALREADY_EXISTS" in str(e):
        print(f"ℹ️ Catalog {CATALOG} already exists, continuing...")
    else:
        print(f"⚠️ Could not create with managed location ({e}), trying without...")
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
        print(f"✅ Created catalog {CATALOG}")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ Created schema {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🚀 Register Model to Unity Catalog with Feature Store

# COMMAND ----------

# DBTITLE 1,Setup Experiment
experiment_name = f"/Users/{user}/range_optimization_feature_store"
mlflow.set_experiment(experiment_name)
print(f"📊 Experiment: {experiment_name}")

# COMMAND ----------

# DBTITLE 1,Log Model with Feature Store Integration
with tempfile.TemporaryDirectory() as tmpdir:
    # Save config artifact
    config_path = os.path.join(tmpdir, "config.json")
    with open(config_path, "w") as f:
        json.dump(asdict(config), f, indent=2)
    
    with mlflow.start_run(run_name="range_optimizer_with_features") as run:
        run_id = run.info.run_id
        print(f"🏃 Run ID: {run_id}")
        
        # Log parameters
        mlflow.log_params({
            "min_facings": config.min_facings,
            "max_facings": config.max_facings,
            "target_service_level": config.target_service_level,
            "safety_factor": config.safety_factor,
            "num_skus": len(training_df),
        })
        
        # Log metrics
        mlflow.log_metrics({
            "total_skus": len(sample_output),
            "skus_ranged": int(sample_output['IS_RANGED'].sum()),
            "total_facings": float(sample_output['RECOMMENDED_FACINGS'].sum()),
            "total_weekly_profit": float(sample_output['EXPECTED_WEEKLY_PROFIT'].sum()),
            "avg_space_productivity": float(sample_output['SPACE_PRODUCTIVITY'].mean()),
        })
        
        # Log metrics by category  
        for category in sample_output['CATEGORY'].dropna().unique():
            cat_data = sample_output[sample_output['CATEGORY'] == category]
            cat_key = category.lower().replace(' ', '_').replace('&', 'and')
            mlflow.log_metric(f"{cat_key}_total_facings", cat_data['RECOMMENDED_FACINGS'].sum())
            mlflow.log_metric(f"{cat_key}_total_profit", cat_data['EXPECTED_WEEKLY_PROFIT'].sum())
        
        # Use fe.log_model() to capture feature store metadata
        print("📤 Registering model to Unity Catalog with Feature Store metadata...")
        model_info = fe.log_model(
            model=RangeOptimizerModel(config=config),
            artifact_path="range_optimizer",
            flavor=mlflow.pyfunc,
            training_set=training_set,
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

# Test with just SKU_IDs - features will be automatically retrieved!
test_data = training_df[['SKU_ID', 'SKU_NAME']].head(5)

print("📥 Test Input (only SKU_IDs):")
display(test_data)

# Model will automatically fetch features from Feature Store
predictions = loaded_model.predict(training_df.head(5))

print("\n📤 Optimization Results (with auto-fetched features):")
display(predictions[['SKU_ID', 'SKU_NAME', 'RECOMMENDED_FACINGS', 'FACINGS_CHANGE', 'CHANGE_TYPE', 'EXPECTED_WEEKLY_PROFIT']])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Results Summary

# COMMAND ----------

# DBTITLE 1,Optimization Summary
print("="*60)
print("💰 OPTIMIZATION RESULTS")
print("="*60)
print(f"\n📊 Overall Summary:")
print(f"   Total SKUs: {len(sample_output)}")
print(f"   SKUs Ranged: {sample_output['IS_RANGED'].sum()}")
print(f"   Total Facings: {sample_output['RECOMMENDED_FACINGS'].sum():.0f}")
print(f"   Total Weekly Profit: ${sample_output['EXPECTED_WEEKLY_PROFIT'].sum():,.2f}")
print(f"   Avg Space Productivity: ${sample_output['SPACE_PRODUCTIVITY'].mean():.2f}")

# By change type
print(f"\n📋 Changes Summary:")
for change_type in ['increased', 'decreased', 'no_change', 'new', 'removed']:
    count = len(sample_output[sample_output['CHANGE_TYPE'] == change_type])
    if count > 0:
        print(f"   • {change_type.title()}: {count} SKUs")

# By category
print(f"\n📁 Results by Category:")
for category in sample_output['CATEGORY'].dropna().unique():
    cat_data = sample_output[sample_output['CATEGORY'] == category]
    print(f"\n   {category}:")
    print(f"      SKUs: {len(cat_data)}")
    print(f"      Total Facings: {cat_data['RECOMMENDED_FACINGS'].sum():.0f}")
    print(f"      Weekly Profit: ${cat_data['EXPECTED_WEEKLY_PROFIT'].sum():,.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Complete!
# MAGIC
# MAGIC **Model successfully registered to Unity Catalog with Feature Store integration!**
# MAGIC
# MAGIC | Property | Value |
# MAGIC |----------|-------|
# MAGIC | Model Path | `main.stock_optimization.range_optimizer` |
# MAGIC | Aliases | `@production`, `@champion` |
# MAGIC | SKU Features | `main.stock_optimization.sku_features` |
# MAGIC | Demand Features | `main.stock_optimization.demand_features` |
# MAGIC
# MAGIC ### ✨ Key Features
# MAGIC
# MAGIC 1. **Automatic Feature Lookup**: Model automatically retrieves features during inference
# MAGIC 2. **Schema Aligned**: Input/output matches MCP app expectations
# MAGIC 3. **Feature Governance**: Unity Catalog controls feature access
# MAGIC
# MAGIC ### Model Input/Output
# MAGIC
# MAGIC **Input** (minimal - features auto-fetched):
# MAGIC ```python
# MAGIC input_df = pd.DataFrame([
# MAGIC     {'SKU_ID': 'SKU3001', 'SKU_NAME': 'Stone & Wood Pacific Ale 6pk'},
# MAGIC     {'SKU_ID': 'SKU4001', 'SKU_NAME': 'Sriracha Original 455ml'},
# MAGIC ])
# MAGIC ```
# MAGIC
# MAGIC **Output**:
# MAGIC - `SKU_ID`, `SKU_NAME`, `CATEGORY`, `SEGMENT`, `BRAND`
# MAGIC - `RECOMMENDED_FACINGS`, `FACINGS_CHANGE`, `CHANGE_TYPE`
# MAGIC - `EXPECTED_WEEKLY_PROFIT`, `SPACE_PRODUCTIVITY`, `IS_RANGED`
# MAGIC
# MAGIC ### Next Steps
# MAGIC
# MAGIC 1. **Deploy Serving Endpoint**: Run `02_deploy_serving_endpoint` notebook
# MAGIC 2. **View Lineage**: Open Catalog Explorer → Models → range_optimizer → Lineage tab