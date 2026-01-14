#!/usr/bin/env python3
"""
Create MLflow Model Using Feature Store Data

This script creates and trains an MLflow model using feature store data
from Unity Catalog. It follows the existing patterns in the codebase
for feature engineering and model training.

Usage:
    # Set environment variables first
    export DATABRICKS_HOST=...
    export DATABRICKS_TOKEN=...
    
    # Run the script
    python create_mlflow_model_with_features.py
    
Prerequisites:
    - Feature tables must exist in Unity Catalog
    - MLflow tracking server configured
    - Proper UC permissions
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any

import pandas as pd
import numpy as np
import mlflow
import mlflow.pyfunc
from mlflow.models.signature import infer_signature
from mlflow import MlflowClient

# Databricks imports
try:
    from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
    from databricks.sdk import WorkspaceClient
    DATABRICKS_AVAILABLE = True
except ImportError:
    print("⚠️  Databricks SDK not available. Using mock data.")
    DATABRICKS_AVAILABLE = False


# ============================================================
# Configuration
# ============================================================

@dataclass
class ModelConfig:
    """Configuration for the range optimizer model"""
    # Feature store configuration
    catalog: str = "smarter_forecasting"
    schema: str = "stock_optimization"
    
    # Feature table names
    sku_features_table: str = "sku_features"
    demand_features_table: str = "demand_features"
    
    # Model parameters
    min_facings: int = 1
    max_facings: int = 6
    target_service_level: float = 0.95
    safety_factor: float = 1.65
    weekly_to_annual: float = 52.0
    holding_cost_rate: float = 0.25
    ordering_cost: float = 50.0
    lead_time_days: int = 7
    
    # MLflow configuration
    experiment_name: str = "/Shared/range_optimizer_feature_store"
    model_name: str = "range_optimizer_fs"
    run_name: str = "range_optimizer_with_feature_store"


@dataclass 
class FeatureSpec:
    """Specification for feature lookup"""
    table_name: str
    lookup_key: str
    feature_names: List[str]


# ============================================================
# MLflow Model Implementation
# ============================================================

class RangeOptimizerModel(mlflow.pyfunc.PythonModel):
    """
    MLflow pyfunc model for range optimization using feature store data.
    
    This model:
    1. Accepts SKU_ID as input
    2. Looks up features from Unity Catalog Feature Store
    3. Calculates optimal facings based on demand and profitability
    4. Returns optimization recommendations
    
    Expected input:
        - DataFrame with SKU_ID column
        
    Expected output:
        - DataFrame with optimization results including facings, metrics
    """
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self.fe_client = None
        
    def load_context(self, context):
        """Load configuration and initialize clients"""
        # Load config from artifacts
        config_path = context.artifacts.get("config")
        if config_path:
            with open(config_path, "r") as f:
                config_dict = json.load(f)
                self.config = ModelConfig(**config_dict)
        else:
            self.config = ModelConfig()
            
        # Initialize feature engineering client
        if DATABRICKS_AVAILABLE:
            self.fe_client = FeatureEngineeringClient()
    
    def predict(self, context, model_input):
        """
        Generate optimization predictions for input SKUs.
        
        Args:
            context: MLflow context
            model_input: DataFrame with SKU_ID column
            
        Returns:
            DataFrame with optimization results
        """
        if not DATABRICKS_AVAILABLE:
            # Return mock predictions for testing
            return self._generate_mock_predictions(model_input)
            
        # Create training set with feature lookups
        training_data = self._create_training_set(model_input)
        
        # Apply optimization algorithm
        results = self._optimize_range(training_data)
        
        return results
    
    def _create_training_set(self, sku_df):
        """Create training set with feature lookups from Unity Catalog"""
        if not self.fe_client:
            raise ValueError("Feature Engineering client not initialized")
            
        # Define feature lookups
        feature_lookups = [
            FeatureLookup(
                table_name=f"{self.config.catalog}.{self.config.schema}.{self.config.sku_features_table}",
                lookup_key="SKU_ID",
                feature_names=[
                    "SKU_NAME", "UNIT_COST", "UNIT_PRICE", "CATEGORY", 
                    "SEGMENT", "BRAND", "PACK_WIDTH_MM", "IS_MUST_STOCK",
                    "IS_PRIVATE_LABEL"
                ]
            ),
            FeatureLookup(
                table_name=f"{self.config.catalog}.{self.config.schema}.{self.config.demand_features_table}",
                lookup_key="SKU_ID", 
                feature_names=[
                    "WEEKLY_UNITS", "DEMAND_STD", "SEASONALITY_INDEX"
                ]
            )
        ]
        
        # Create training set
        training_set = self.fe_client.create_training_set(
            df=sku_df,
            feature_lookups=feature_lookups,
            label=None,  # Unsupervised optimization
            exclude_columns=["SKU_ID"]
        )
        
        return training_set.load_df().toPandas()
    
    def _optimize_range(self, data):
        """Apply range optimization algorithm to the data"""
        results = []
        
        for _, row in data.iterrows():
            # Calculate margin per unit
            margin_per_unit = row.get('UNIT_PRICE', 0) - row.get('UNIT_COST', 0)
            
            # Calculate weekly profit
            weekly_units = row.get('WEEKLY_UNITS', 0)
            weekly_profit = weekly_units * margin_per_unit
            
            # Calculate demand volatility factor
            demand_std = row.get('DEMAND_STD', 0)
            volatility_factor = 1.0
            if weekly_units > 0:
                volatility_factor = min(2.0, 1.0 + (demand_std / weekly_units))
            
            # Calculate space productivity score
            pack_width = row.get('PACK_WIDTH_MM', 100)
            space_productivity = (weekly_profit * volatility_factor) / pack_width if pack_width > 0 else 0
            
            # Calculate optimal facings
            is_must_stock = row.get('IS_MUST_STOCK', False)
            
            if space_productivity <= 0 or weekly_units <= 0:
                optimal_facings = self.config.min_facings if is_must_stock else 0
            else:
                # Base facings on space productivity (normalized)
                base_facings = int(space_productivity / 100)  # Scale factor
                optimal_facings = max(
                    self.config.min_facings if is_must_stock else 0,
                    min(self.config.max_facings, base_facings)
                )
            
            # Calculate safety stock requirements
            safety_stock = max(0, self.config.safety_factor * demand_std * 
                             np.sqrt(self.config.lead_time_days / 7))
            
            # Calculate expected metrics
            expected_weekly_profit = optimal_facings * weekly_profit
            expected_weekly_units = optimal_facings * weekly_units
            total_weekly_cost = (optimal_facings * weekly_units * row.get('UNIT_COST', 0) * 
                               self.config.holding_cost_rate / self.config.weekly_to_annual)
            
            results.append({
                'SKU_ID': row.get('SKU_ID', ''),
                'SKU_NAME': row.get('SKU_NAME', ''),
                'CATEGORY': row.get('CATEGORY', ''),
                'OPTIMAL_FACINGS': optimal_facings,
                'SPACE_PRODUCTIVITY': round(space_productivity, 2),
                'EXPECTED_WEEKLY_PROFIT': round(expected_weekly_profit, 2),
                'EXPECTED_WEEKLY_UNITS': round(expected_weekly_units, 2),
                'SAFETY_STOCK': round(safety_stock, 2),
                'TOTAL_WEEKLY_COST': round(total_weekly_cost, 2),
                'NET_WEEKLY_PROFIT': round(expected_weekly_profit - total_weekly_cost, 2),
                'MARGIN_PER_UNIT': round(margin_per_unit, 2),
                'WEEKLY_DEMAND': round(weekly_units, 2),
                'DEMAND_VOLATILITY': round(volatility_factor, 2)
            })
        
        return pd.DataFrame(results)
    
    def _generate_mock_predictions(self, model_input):
        """Generate mock predictions for testing without Databricks"""
        results = []
        
        for _, row in model_input.iterrows():
            sku_id = row.get('SKU_ID', f'SKU_{len(results)}')
            
            # Mock optimization results
            optimal_facings = np.random.randint(1, self.config.max_facings + 1)
            expected_profit = np.random.uniform(100, 1000) * optimal_facings
            weekly_units = np.random.uniform(10, 100)
            
            results.append({
                'SKU_ID': sku_id,
                'SKU_NAME': f'Product {sku_id}',
                'CATEGORY': 'Mock Category',
                'OPTIMAL_FACINGS': optimal_facings,
                'SPACE_PRODUCTIVITY': round(np.random.uniform(50, 500), 2),
                'EXPECTED_WEEKLY_PROFIT': round(expected_profit, 2),
                'EXPECTED_WEEKLY_UNITS': round(weekly_units * optimal_facings, 2),
                'SAFETY_STOCK': round(np.random.uniform(5, 50), 2),
                'TOTAL_WEEKLY_COST': round(expected_profit * 0.1, 2),
                'NET_WEEKLY_PROFIT': round(expected_profit * 0.9, 2),
                'MARGIN_PER_UNIT': round(np.random.uniform(1, 10), 2),
                'WEEKLY_DEMAND': round(weekly_units, 2),
                'DEMAND_VOLATILITY': round(np.random.uniform(1.0, 2.0), 2)
            })
        
        return pd.DataFrame(results)


# ============================================================
# Training and Registration Functions
# ============================================================

def create_sample_skus():
    """Create sample SKU data for testing"""
    skus = [
        'SKU1001', 'SKU1002', 'SKU1003', 'SKU1004', 'SKU1005',
        'SKU2001', 'SKU2002', 'SKU2003', 'SKU2004', 'SKU2005'
    ]
    return pd.DataFrame({'SKU_ID': skus})


def train_and_register_model(config: ModelConfig):
    """Train and register the MLflow model"""
    
    # Configure MLflow
    if DATABRICKS_AVAILABLE:
        mlflow.set_registry_uri("databricks-uc")
    else:
        mlflow.set_tracking_uri("file:./mlruns")
        
    mlflow.set_experiment(config.experiment_name)
    
    # Create sample training data
    sample_skus = create_sample_skus()
    
    print(f"🎯 Training model with {len(sample_skus)} sample SKUs")
    print(f"📊 Experiment: {config.experiment_name}")
    print(f"📦 Model: {config.model_name}")
    
    with mlflow.start_run(run_name=config.run_name) as run:
        print(f"🚀 Started MLflow run: {run.info.run_id}")
        
        # Log parameters
        params = asdict(config)
        mlflow.log_params(params)
        
        # Create model instance
        model = RangeOptimizerModel(config)
        
        # Generate predictions for sample data
        predictions = model.predict(None, sample_skus)
        
        # Calculate and log metrics
        total_facings = predictions['OPTIMAL_FACINGS'].sum()
        total_profit = predictions['EXPECTED_WEEKLY_PROFIT'].sum()
        avg_facings = predictions['OPTIMAL_FACINGS'].mean()
        
        mlflow.log_metric("total_skus", len(predictions))
        mlflow.log_metric("total_facings", total_facings)
        mlflow.log_metric("total_expected_profit", total_profit)
        mlflow.log_metric("avg_facings_per_sku", avg_facings)
        
        # Log metrics by category
        for category in predictions['CATEGORY'].unique():
            if pd.notna(category):
                cat_data = predictions[predictions['CATEGORY'] == category]
                mlflow.log_metric(f"{category}_facings", cat_data['OPTIMAL_FACINGS'].sum())
                mlflow.log_metric(f"{category}_profit", cat_data['EXPECTED_WEEKLY_PROFIT'].sum())
        
        # Save config as artifact
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            with open(config_path, "w") as f:
                json.dump(params, f, indent=2)
            
            # Log model with config artifact
            signature = infer_signature(sample_skus, predictions)
            
            model_info = mlflow.pyfunc.log_model(
                "model",
                flavor=mlflow.pyfunc,
                python_model=model,
                artifacts={"config": str(config_path)},
                signature=signature,
                input_example=sample_skus.head(1)
            )
            
            print(f"✅ Model logged to: {model_info.model_uri}")
        
        # Register model to Unity Catalog (if available)
        if DATABRICKS_AVAILABLE:
            uc_model_path = f"{config.catalog}.{config.schema}.{config.model_name}"
            
            # Register model
            registered_model = mlflow.register_model(
                model_info.model_uri,
                uc_model_path
            )
            
            print(f"📋 Model registered to: {uc_model_path}")
            print(f"🏷️  Version: {registered_model.version}")
            
            # Set to staging for testing
            client = MlflowClient()
            client.set_registered_model_alias(
                uc_model_path, 
                "staging", 
                registered_model.version
            )
            
            print(f"🎯 Set version {registered_model.version} to staging")
        
        return model_info.model_uri, run.info.run_id


# ============================================================
# Main Execution
# ============================================================

def main():
    """Main execution function"""
    print("🏪 Creating MLflow Model with Feature Store Data")
    print("=" * 50)
    
    # Initialize configuration
    config = ModelConfig()
    
    # Override with environment variables if available
    config.catalog = os.getenv("CATALOG", config.catalog)
    config.schema = os.getenv("SCHEMA", config.schema)
    config.experiment_name = os.getenv("EXPERIMENT_NAME", config.experiment_name)
    
    print(f"📊 Catalog: {config.catalog}")
    print(f"📋 Schema: {config.schema}")
    print(f"🧪 Experiment: {config.experiment_name}")
    print()
    
    try:
        # Train and register model
        model_uri, run_id = train_and_register_model(config)
        
        print()
        print("🎉 Model creation completed successfully!")
        print("=" * 50)
        print(f"🔗 Model URI: {model_uri}")
        print(f"🆔 Run ID: {run_id}")
        
        if DATABRICKS_AVAILABLE:
            print(f"📦 UC Model: {config.catalog}.{config.schema}.{config.model_name}")
            print()
            print("📖 To load the model in production:")
            print(f"   model = mlflow.pyfunc.load_model('models:/{config.catalog}.{config.schema}.{config.model_name}@staging')")
        else:
            print()
            print("📖 To load the model locally:")
            print(f"   model = mlflow.pyfunc.load_model('{model_uri}')")
        
        print()
        print("🧪 To test the model:")
        print("   import pandas as pd")
        print("   test_data = pd.DataFrame({'SKU_ID': ['SKU1001', 'SKU1002']})")
        print("   predictions = model.predict(None, test_data)")
        
    except Exception as e:
        print(f"❌ Error creating model: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())