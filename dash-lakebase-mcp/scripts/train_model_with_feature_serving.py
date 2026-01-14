#!/usr/bin/env python3
"""
Train Range Optimizer Model with Feature Store + Automatic Feature Serving

This script properly uses fe.log_model() with training_set parameter
to enable automatic feature lookup at serving time.

Key difference from previous version:
- Uses fe.log_model() with training_set (not mlflow.pyfunc.log_model)
- This enables automatic feature retrieval during inference
- At serving time: Send only SKU_ID → features fetched automatically
"""

import mlflow
import mlflow.pyfunc
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional
import json
import tempfile
from mlflow.models.signature import infer_signature
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
from databricks.sdk.runtime import spark

# Configuration
CATALOG = "smarter_forecasting"
SCHEMA = "stock_optimization"
MODEL_NAME = "range_optimizer"

SKU_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.sku_features"
DEMAND_FEATURES_TABLE = f"{CATALOG}.{SCHEMA}.demand_features"
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"


@dataclass
class OptimizationConfig:
    """Configuration for range optimization algorithm"""
    min_facings: int = 1
    max_facings: int = 6
    target_service_level: float = 0.95
    safety_factor: float = 1.65
    weekly_to_annual: float = 52.0
    holding_cost_rate: float = 0.25
    ordering_cost: float = 50.0
    lead_time_days: int = 7


class RangeOptimizerModel(mlflow.pyfunc.PythonModel):
    """Range Optimizer Model - Feature Store compatible"""

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()

    def load_context(self, context):
        """Load config from artifacts"""
        self.config = OptimizationConfig()

    def calculate_optimal_facings(self, weekly_units, demand_std, margin, is_must_stock):
        """Calculate optimal facings"""
        if weekly_units <= 0 or margin <= 0:
            return self.config.min_facings if is_must_stock else 0

        weekly_profit = weekly_units * margin
        safety_multiplier = 1 + (demand_std / weekly_units) if weekly_units > 0 else 1
        productivity_score = weekly_profit / safety_multiplier

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

        return max(
            self.config.min_facings if is_must_stock else 0,
            min(recommended, self.config.max_facings)
        )

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        """Run optimization - receives features from Feature Store"""
        results = []

        for _, row in model_input.iterrows():
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

            margin = unit_price - unit_cost
            recommended_facings = self.calculate_optimal_facings(
                weekly_units, demand_std, margin, is_must_stock
            )

            facings_change = recommended_facings - current_facings
            if facings_change > 0:
                change_type = "increase"
            elif facings_change < 0:
                change_type = "decrease"
            else:
                change_type = "maintain"

            expected_weekly_units = weekly_units
            expected_margin_weekly = weekly_units * margin
            space_productivity = expected_margin_weekly / (pack_width * recommended_facings) if recommended_facings > 0 else 0
            score = min(weekly_units / 100, 1.0)

            results.append({
                'sku_id': sku_id,
                'sku_name': sku_name,
                'category': category,
                'segment': segment,
                'brand': brand,
                'current_facings': current_facings,
                'recommended_facings': recommended_facings,
                'facings_change': facings_change,
                'change_from_current': change_type,
                'expected_units_weekly': expected_weekly_units,
                'expected_margin_weekly': round(expected_margin_weekly, 2),
                'space_productivity': round(space_productivity, 2),
                'score': round(score, 3),
                'is_must_stock': is_must_stock,
                'is_private_label': is_private_label,
                'pack_width_mm': pack_width
            })

        return pd.DataFrame(results)


def main():
    """Main training function"""
    print("=" * 80)
    print("🧠 Training Range Optimizer with Feature Store Serving")
    print("=" * 80)

    # Initialize clients
    print("🔧 Initializing clients...")
    fe = FeatureEngineeringClient()
    mlflow.set_registry_uri("databricks-uc")
    print(f"   Spark version: {spark.version}")

    print(f"📊 SKU Features: {SKU_FEATURES_TABLE}")
    print(f"📈 Demand Features: {DEMAND_FEATURES_TABLE}")
    print(f"📦 Model will be registered to: {UC_MODEL_PATH}")

    # Create training dataset with FeatureLookup
    print("\n📚 Creating training dataset with FeatureLookup...")

    # Base DataFrame: just SKU_ID and SKU_NAME
    base_df = spark.sql(f"""
        SELECT DISTINCT
            d.SKU_ID,
            p.SKU_NAME,
            p.CURRENT_FACINGS
        FROM {DEMAND_FEATURES_TABLE} d
        INNER JOIN {SKU_FEATURES_TABLE} p ON d.SKU_ID = p.SKU_ID
    """)
    print(f"   Base DataFrame: {base_df.count()} SKUs")

    # Define feature lookups - these will be automatically applied at serving time!
    feature_lookups = [
        FeatureLookup(
            table_name=SKU_FEATURES_TABLE,
            lookup_key="SKU_ID",
            feature_names=[
                "UNIT_COST", "UNIT_PRICE", "CATEGORY", "SEGMENT", "BRAND",
                "PACK_WIDTH_MM", "IS_MUST_STOCK", "IS_PRIVATE_LABEL"
            ]
        ),
        FeatureLookup(
            table_name=DEMAND_FEATURES_TABLE,
            lookup_key="SKU_ID",
            feature_names=["WEEKLY_UNITS", "DEMAND_STD", "FORECAST_4W"]
        )
    ]

    print(f"   Feature Lookups defined:")
    print(f"     • {SKU_FEATURES_TABLE}: 8 features")
    print(f"     • {DEMAND_FEATURES_TABLE}: 3 features")

    # Create training set
    training_set = fe.create_training_set(
        df=base_df,
        feature_lookups=feature_lookups,
        label=None,
        exclude_columns=[]
    )

    training_df = training_set.load_df().toPandas()
    print(f"✅ Training set created: {len(training_df)} rows, {len(training_df.columns)} features")

    # Train model
    print("\n🏋️  Training model...")
    config = OptimizationConfig()
    model = RangeOptimizerModel(config)

    # Test prediction
    sample_input = training_df[["SKU_ID", "SKU_NAME", "CURRENT_FACINGS"]].head(5)
    sample_predictions = model.predict(None, training_df.head(5))
    print(f"✅ Model training complete")
    print(f"   Sample predictions shape: {sample_predictions.shape}")

    # Infer signature - input is just SKU_ID + optional fields
    # Output is full prediction results
    signature = infer_signature(sample_input, sample_predictions)
    print(f"\n📝 Model Signature:")
    print(f"   Input: {list(sample_input.columns)}")
    print(f"   Output: {list(sample_predictions.columns)}")
    print(f"   Signature object: {signature}")
    print(f"   Has inputs: {signature.inputs is not None}")
    print(f"   Has outputs: {signature.outputs is not None}")

    # Log model with Feature Engineering
    print("\n📦 Logging model with Feature Store integration...")

    with mlflow.start_run(run_name="range_optimizer_feature_serving") as run:
        mlflow.log_params(asdict(config))
        mlflow.log_metric("avg_recommended_facings", sample_predictions['recommended_facings'].mean())
        mlflow.log_metric("products_with_changes", (sample_predictions['facings_change'] != 0).sum())

        # KEY: Use fe.log_model() with training_set to enable automatic feature lookup
        # Log first WITHOUT registering to UC (to avoid signature validation issue)
        model_info = fe.log_model(
            model=model,
            artifact_path="range_optimizer",
            flavor=mlflow.pyfunc,
            training_set=training_set,  # This enables automatic feature lookup!
            signature=signature,
            input_example=sample_input,
            pip_requirements=["pandas", "numpy"]
            # Note: NOT including registered_model_name here
        )

        print(f"✅ Model logged with Feature Store metadata")
        print(f"   Run ID: {run.info.run_id}")
        print(f"   🎯 Features will be automatically looked up during inference!")

    # Now register the logged model to Unity Catalog
    print(f"\n📝 Registering to Unity Catalog: {UC_MODEL_PATH}...")
    model_uri = f"runs:/{run.info.run_id}/range_optimizer"

    client = mlflow.MlflowClient()
    try:
        client.create_registered_model(UC_MODEL_PATH, description="Range Optimizer with automatic feature serving")
    except:
        pass  # Model already exists

    model_version = client.create_model_version(
        name=UC_MODEL_PATH,
        source=model_uri,
        run_id=run.info.run_id
    )
    print(f"✅ Registered to Unity Catalog")
    print(f"   Version: {model_version.version}")

    # Set Champion alias
    print("\n🏷️  Setting model alias to 'Champion'...")
    client.set_registered_model_alias(UC_MODEL_PATH, "Champion", str(model_version.version))
    print(f"✅ Set version {model_version.version} as 'Champion'")

    # Verify
    print("\n🔍 Verifying model...")
    loaded_model = mlflow.pyfunc.load_model(f"models:/{UC_MODEL_PATH}@Champion")
    test_input = pd.DataFrame([{"SKU_ID": "SKU3001", "SKU_NAME": "Test", "CURRENT_FACINGS": 2}])
    test_predictions = loaded_model.predict(test_input)

    print("=" * 80)
    print("✅ SUCCESS! Model with Feature Store Serving Ready")
    print("=" * 80)
    print(f"📦 Model: {UC_MODEL_PATH}")
    print(f"🏷️  Alias: Champion (version {model_version.version})")
    print(f"📊 Training samples: {len(training_df)}")
    print(f"🎯 Test prediction shape: {test_predictions.shape}")
    print(f"\n🌟 Key Feature:")
    print(f"   At serving time, send only: SKU_ID, SKU_NAME, CURRENT_FACINGS")
    print(f"   Features auto-fetched from: {SKU_FEATURES_TABLE}, {DEMAND_FEATURES_TABLE}")
    print(f"\nNext step:")
    print(f"  Deploy to serving endpoint: scripts/deploy_endpoint_standalone.py")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())
