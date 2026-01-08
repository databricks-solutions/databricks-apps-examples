"""
Deploy Stock Optimization Model to Databricks MLflow

This script packages and deploys the stock optimization model to
Databricks MLflow Model Serving.

Usage:
    python deploy_model_to_mlflow.py [--model-name MODEL_NAME] [--endpoint-name ENDPOINT_NAME]
"""

import argparse
import mlflow
import mlflow.pyfunc
import pandas as pd
import numpy as np
import os
from databricks.sdk import WorkspaceClient
from src.dash_dbx_writeback.ml.stock_optimizer import StockOptimizer, OptimizationConfig

# Enable Databricks SDK for UC model artifacts (for GovCloud/special configurations)
os.environ["MLFLOW_USE_DATABRICKS_SDK_MODEL_ARTIFACTS_REPO_FOR_UC"] = "True"


class StockOptimizationModel(mlflow.pyfunc.PythonModel):
    """
    MLflow wrapper for the Stock Optimization model.
    This allows the model to be served via Databricks Model Serving.
    """

    def __init__(self):
        """Initialize the model with default configuration"""
        self.config = OptimizationConfig(
            holding_cost_rate=0.25,
            ordering_cost=50.0,
            lead_time_days=7,
            service_level=0.95,
            safety_factor=1.65,
            max_storage_capacity=10000,
        )
        self.optimizer = StockOptimizer(config=self.config)

    def predict(self, context, model_input):
        """
        Predict/optimize stock levels based on input forecast data.

        Args:
            context: MLflow context (not used)
            model_input: pandas DataFrame with forecast data

        Returns:
            pandas DataFrame with optimization results
        """
        # If input is a pandas DataFrame, use it directly
        if isinstance(model_input, pd.DataFrame):
            forecast_df = model_input
        else:
            # Convert to DataFrame if needed
            forecast_df = pd.DataFrame(model_input)

        # Run optimization
        result_df = self.optimizer.optimize_inventory(forecast_df)

        return result_df


def create_sample_input():
    """Create sample input data for model signature"""
    return pd.DataFrame({
        'SELL_ID': ['SELL001', 'SELL002'],
        'PRODUCT_NAME': ['Sample Product 1', 'Sample Product 2'],
        'AVG_DAILY_DEMAND': [100.0, 200.0],
        'DEMAND_STD': [15.0, 30.0],
        'TOTAL_FORECAST_30D': [3000.0, 6000.0],
        'UNIT_COST': [10.0, 15.0],
        'SELLING_PRICE': [20.0, 30.0],
    })


def create_sample_output():
    """Create sample output data for model signature"""
    return pd.DataFrame({
        'SELL_ID': ['SELL001', 'SELL002'],
        'PRODUCT_NAME': ['Sample Product 1', 'Sample Product 2'],
        'AVG_DAILY_DEMAND': [100.0, 200.0],
        'OPTIMAL_ORDER_QTY': [500.0, 700.0],
        'SAFETY_STOCK': [50.0, 80.0],
        'REORDER_POINT': [150.0, 280.0],
        'MAX_STOCK_LEVEL': [550.0, 780.0],
        'ANNUAL_HOLDING_COST': [750.0, 1500.0],
        'ANNUAL_ORDERING_COST': [250.0, 400.0],
        'TOTAL_ANNUAL_COST': [1000.0, 1900.0],
        'EXPECTED_ANNUAL_REVENUE': [730000.0, 2190000.0],
        'EXPECTED_ANNUAL_PROFIT': [365000.0, 1095000.0],
        'TURNOVER_RATE': [66.36, 93.59],
        'SERVICE_LEVEL': [0.95, 0.95],
    })


def deploy_model(model_name: str = "coles_inventory.models.stock_optimization_model", endpoint_name: str = "stock-optimization-model"):
    """
    Deploy the stock optimization model to MLflow.

    Args:
        model_name: Name for the registered model
        endpoint_name: Name for the serving endpoint
    """
    print("=" * 70)
    print("DEPLOYING STOCK OPTIMIZATION MODEL TO MLFLOW")
    print("=" * 70)

    # Initialize Databricks workspace client
    w = WorkspaceClient()
    print(f"✓ Connected to Databricks workspace: {w.config.host}")

    # Set MLflow tracking URI to Databricks
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")  # Use Unity Catalog Model Registry
    print(f"✓ MLflow tracking URI set to: databricks")
    print(f"✓ MLflow registry URI set to: databricks-uc (Unity Catalog Model Registry)")

    # Set or create experiment
    experiment_name = "/Users/david.okeeffe@databricks.com/stock-optimization"
    try:
        experiment_id = mlflow.create_experiment(experiment_name)
        print(f"✓ Created new experiment: {experiment_name}")
    except Exception:
        experiment = mlflow.get_experiment_by_name(experiment_name)
        experiment_id = experiment.experiment_id
        print(f"✓ Using existing experiment: {experiment_name}")

    mlflow.set_experiment(experiment_name)

    # Create model instance
    print("\n→ Creating model instance...")
    model = StockOptimizationModel()
    print("✓ Model instance created")

    # Create sample data for model signature
    print("\n→ Creating model signature...")
    sample_input = create_sample_input()
    sample_output = create_sample_output()

    signature = mlflow.models.infer_signature(sample_input, sample_output)
    print("✓ Model signature created")

    # Log the model to MLflow
    print(f"\n→ Logging model to MLflow as '{model_name}'...")

    with mlflow.start_run(run_name="stock-optimization-deployment") as run:
        # Log parameters
        mlflow.log_param("holding_cost_rate", 0.25)
        mlflow.log_param("ordering_cost", 50.0)
        mlflow.log_param("lead_time_days", 7)
        mlflow.log_param("service_level", 0.95)
        mlflow.log_param("max_storage_capacity", 10000)

        # Log the model
        mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=model,
            signature=signature,
            input_example=sample_input,  # Required for Unity Catalog
            registered_model_name=model_name,
            pip_requirements=[
                "numpy",
                "pandas",
            ],
        )

        run_id = run.info.run_id
        print(f"✓ Model logged with run_id: {run_id}")

    print("\n" + "=" * 70)
    print("MODEL DEPLOYMENT INSTRUCTIONS")
    print("=" * 70)
    print("\n📋 Next steps to create a serving endpoint:\n")
    print("1. Go to Databricks workspace → Machine Learning → Serving")
    print("2. Click 'Create serving endpoint'")
    print(f"3. Name: {endpoint_name}")
    print(f"4. Model: {model_name}")
    print("5. Model version: Latest (or specific version)")
    print("6. Compute: Choose appropriate size (e.g., Small)")
    print("7. Click 'Create'")
    print("\n⏱  Wait for the endpoint to become 'Ready' (may take 5-10 minutes)")
    print(f"\n🔗 Then your app will use the endpoint at: /serving-endpoints/{endpoint_name}/invocations")

    print("\n" + "=" * 70)
    print("ALTERNATIVE: Using Databricks CLI")
    print("=" * 70)
    print("\nYou can also create the endpoint using the CLI:\n")
    print(f"""
databricks serving-endpoints create \\
  --name {endpoint_name} \\
  --config '{{
    "served_entities": [{{
      "entity_name": "{model_name}",
      "entity_version": "1",
      "workload_size": "Small",
      "scale_to_zero_enabled": true
    }}]
  }}'
""")

    print("\n✅ Model deployment complete!")
    print(f"   Model Name: {model_name}")
    print(f"   Run ID: {run_id}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Deploy Stock Optimization Model to MLflow")
    parser.add_argument(
        "--model-name",
        type=str,
        default="coles_inventory.models.stock_optimization_model",
        help="Name for the registered model (Unity Catalog: catalog.schema.model)"
    )
    parser.add_argument(
        "--endpoint-name",
        type=str,
        default="stock-optimization-model",
        help="Name for the serving endpoint"
    )

    args = parser.parse_args()

    try:
        deploy_model(model_name=args.model_name, endpoint_name=args.endpoint_name)
    except Exception as e:
        print(f"\n❌ Error during deployment: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
