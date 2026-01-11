#!/usr/bin/env python3
"""
Register Model to Unity Catalog

This script registers the locally trained model to Unity Catalog in Databricks.
It can be run from a Databricks notebook or locally with Databricks credentials.

Usage (Databricks notebook):
    %run ./register_to_uc

Usage (local with databricks-connect):
    cd mcp_app
    uv run python scripts/register_to_uc.py --catalog main --schema stock_optimization

Environment Variables Required:
    DATABRICKS_HOST: Your Databricks workspace URL
    DATABRICKS_TOKEN: Your Databricks access token (or use databricks-cli auth)
"""

import os
import sys
import argparse
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd
import mlflow
import mlflow.pyfunc
from mlflow.models.signature import infer_signature

# Add the src directory to the path for imports
script_dir = Path(__file__).parent
src_dir = script_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from range_optimizer.backend.sample_data import INITIAL_DATA


# ============================================================
# Configuration
# ============================================================

@dataclass
class OptimizationConfig:
    """Configuration parameters for stock optimization"""
    holding_cost_rate: float = 0.25
    ordering_cost: float = 50.0
    lead_time_days: int = 7
    service_level: float = 0.95
    safety_factor: float = 1.65
    max_storage_capacity: int = 10000


# ============================================================
# MLflow PyFunc Model (same as local training)
# ============================================================

class StockOptimizerModel(mlflow.pyfunc.PythonModel):
    """Stock optimization model using Economic Order Quantity (EOQ)."""
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
    
    def load_context(self, context):
        config_path = context.artifacts.get("config")
        if config_path:
            with open(config_path, "r") as f:
                config_dict = json.load(f)
                self.config = OptimizationConfig(**config_dict)
        else:
            self.config = OptimizationConfig()
    
    def calculate_eoq(self, annual_demand: float, ordering_cost: float,
                     unit_cost: float, holding_cost_rate: float) -> float:
        if annual_demand <= 0 or unit_cost <= 0:
            return 0.0
        return np.sqrt((2 * annual_demand * ordering_cost) / (holding_cost_rate * unit_cost))
    
    def calculate_safety_stock(self, demand_std: float, lead_time_days: int,
                               safety_factor: float) -> float:
        if demand_std <= 0:
            return 0.0
        return safety_factor * demand_std * np.sqrt(lead_time_days)
    
    def calculate_reorder_point(self, avg_daily_demand: float, lead_time_days: int,
                               safety_stock: float) -> float:
        return (avg_daily_demand * lead_time_days) + safety_stock
    
    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        results = []
        
        for _, row in model_input.iterrows():
            sell_id = row.get('SELL_ID', 'UNKNOWN')
            product_name = row.get('PRODUCT_NAME', 'Unknown Product')
            avg_daily_demand = float(row.get('AVG_DAILY_DEMAND', 0))
            demand_std = float(row.get('DEMAND_STD', avg_daily_demand * 0.2))
            unit_cost = float(row.get('UNIT_COST', 10.0))
            selling_price = float(row.get('SELLING_PRICE', unit_cost * 2))
            
            annual_demand = avg_daily_demand * 365
            
            eoq = self.calculate_eoq(
                annual_demand, self.config.ordering_cost,
                unit_cost, self.config.holding_cost_rate
            )
            
            safety_stock = self.calculate_safety_stock(
                demand_std, self.config.lead_time_days, self.config.safety_factor
            )
            
            reorder_point = self.calculate_reorder_point(
                avg_daily_demand, self.config.lead_time_days, safety_stock
            )
            
            optimal_order_qty = min(eoq, self.config.max_storage_capacity)
            max_stock_level = optimal_order_qty + safety_stock
            
            avg_inventory = optimal_order_qty / 2 + safety_stock
            annual_holding_cost = avg_inventory * unit_cost * self.config.holding_cost_rate
            annual_ordering_cost = (annual_demand / optimal_order_qty) * self.config.ordering_cost if optimal_order_qty > 0 else 0
            total_annual_cost = annual_holding_cost + annual_ordering_cost
            
            expected_annual_revenue = annual_demand * selling_price
            expected_annual_profit = expected_annual_revenue - (annual_demand * unit_cost) - total_annual_cost
            
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
                'EXPECTED_ANNUAL_REVENUE': round(expected_annual_revenue, 2),
                'EXPECTED_ANNUAL_PROFIT': round(expected_annual_profit, 2),
                'TURNOVER_RATE': round(turnover_rate, 2),
                'SERVICE_LEVEL': self.config.service_level,
            })
        
        return pd.DataFrame(results)


# ============================================================
# Data Generation
# ============================================================

def generate_forecast_from_products(products):
    """Generate realistic forecast data from product data."""
    np.random.seed(42)
    
    category_demand_multipliers = {
        'Beer & Seltzer': 8.0,
        'Hot Sauce': 2.5,
        'Ice Cream': 5.0,
    }
    
    subcategory_variance = {
        'Craft Beer': 0.35, 'Hard Seltzer': 0.25, 'Asian Style': 0.20,
        'Louisiana Style': 0.15, 'Mexican Style': 0.20, 'Extreme Heat': 0.50,
        'Craft/Artisan': 0.40, 'Premium Pints': 0.30, 'Premium Tubs': 0.25,
        'Low-Cal Pints': 0.35, 'Sticks/Bars': 0.20,
    }
    
    price_tiers = {
        'Premium': {'unit_cost': 12.0, 'margin': 0.45},
        'Core': {'unit_cost': 8.0, 'margin': 0.35},
        'Niche': {'unit_cost': 15.0, 'margin': 0.55},
    }
    
    forecast_data = []
    
    for product in products:
        shelf_space = product['SHELF_SPACE_CM']
        category = product['CATEGORY_NAME']
        subcategory = product['SUBCATEGORY_NAME']
        loyalty_group = product['LOYALTY_GROUP']
        
        demand_multiplier = category_demand_multipliers.get(category, 3.0)
        base_demand = shelf_space * demand_multiplier * np.random.uniform(0.8, 1.2)
        
        variance_multiplier = subcategory_variance.get(subcategory, 0.25)
        demand_std = base_demand * variance_multiplier
        
        pricing = price_tiers.get(loyalty_group, price_tiers['Core'])
        unit_cost = pricing['unit_cost'] * np.random.uniform(0.9, 1.1)
        selling_price = unit_cost * (1 + pricing['margin'])
        
        forecast_data.append({
            'SELL_ID': product['SELL_ID'],
            'PRODUCT_NAME': product['PRODUCT_NAME'],
            'AVG_DAILY_DEMAND': round(base_demand, 2),
            'DEMAND_STD': round(demand_std, 2),
            'TOTAL_FORECAST_30D': round(base_demand * 30, 2),
            'UNIT_COST': round(unit_cost, 2),
            'SELLING_PRICE': round(selling_price, 2),
            'CATEGORY_NAME': category,
            'SUBCATEGORY_NAME': subcategory,
            'SHELF_SPACE_CM': shelf_space,
        })
    
    return pd.DataFrame(forecast_data)


# ============================================================
# Registration Functions
# ============================================================

def register_to_unity_catalog(catalog: str, schema: str, model_name: str = "stock_optimizer"):
    """
    Register the model to Unity Catalog.
    """
    uc_model_path = f"{catalog}.{schema}.{model_name}"
    
    print(f"\n{'='*60}")
    print("REGISTERING MODEL TO UNITY CATALOG")
    print(f"{'='*60}")
    print(f"Target: {uc_model_path}")
    
    # Set MLflow to use Unity Catalog
    mlflow.set_registry_uri("databricks-uc")
    
    # Generate training data
    print("\n→ Generating training data...")
    forecast_df = generate_forecast_from_products(INITIAL_DATA)
    print(f"✓ Generated {len(forecast_df)} products")
    
    # Create model and get signature
    config = OptimizationConfig()
    model = StockOptimizerModel(config=config)
    
    print("→ Computing model signature...")
    sample_output = model.predict(None, forecast_df)
    signature = infer_signature(forecast_df, sample_output)
    print("✓ Signature computed")
    
    # Create experiment for Unity Catalog
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        user = w.current_user.me().user_name
        experiment_name = f"/Users/{user}/stock_optimization_uc"
    except Exception:
        experiment_name = "/Shared/stock_optimization_uc"
    
    mlflow.set_experiment(experiment_name)
    print(f"→ Using experiment: {experiment_name}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save config artifact
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump(asdict(config), f, indent=2)
        
        artifacts = {"config": config_path}
        
        with mlflow.start_run(run_name="stock_optimizer_uc_registration") as run:
            print(f"→ MLflow Run ID: {run.info.run_id}")
            
            # Log parameters
            mlflow.log_param("holding_cost_rate", config.holding_cost_rate)
            mlflow.log_param("ordering_cost", config.ordering_cost)
            mlflow.log_param("lead_time_days", config.lead_time_days)
            mlflow.log_param("service_level", config.service_level)
            mlflow.log_param("safety_factor", config.safety_factor)
            mlflow.log_param("num_products", len(forecast_df))
            
            # Log metrics
            mlflow.log_metric("total_products", len(sample_output))
            mlflow.log_metric("avg_optimal_order_qty", sample_output['OPTIMAL_ORDER_QTY'].mean())
            mlflow.log_metric("total_annual_cost", sample_output['TOTAL_ANNUAL_COST'].sum())
            mlflow.log_metric("total_annual_profit", sample_output['EXPECTED_ANNUAL_PROFIT'].sum())
            
            # Log the model with UC registration
            print("→ Logging and registering model to Unity Catalog...")
            model_info = mlflow.pyfunc.log_model(
                artifact_path="stock_optimizer",
                python_model=StockOptimizerModel(config=config),
                artifacts=artifacts,
                signature=signature,
                input_example=forecast_df.head(3),
                pip_requirements=["numpy", "pandas"],
                registered_model_name=uc_model_path,
            )
            
            print(f"✓ Model registered: {model_info.model_uri}")
    
    # Set aliases
    print("→ Setting model aliases...")
    try:
        from mlflow import MlflowClient
        client = MlflowClient()
        
        versions = client.search_model_versions(f"name='{uc_model_path}'")
        if versions:
            latest_version = max([int(v.version) for v in versions])
            client.set_registered_model_alias(uc_model_path, "production", latest_version)
            client.set_registered_model_alias(uc_model_path, "champion", latest_version)
            print(f"✓ Set 'production' and 'champion' aliases to v{latest_version}")
    except Exception as e:
        print(f"⚠️  Could not set aliases: {e}")
    
    print(f"\n{'='*60}")
    print("✅ REGISTRATION COMPLETE")
    print(f"{'='*60}")
    print(f"\nModel Path: {uc_model_path}")
    print(f"\nTo use the model:")
    print(f'  model = mlflow.pyfunc.load_model("models:/{uc_model_path}@production")')
    
    return uc_model_path


def main():
    parser = argparse.ArgumentParser(description="Register Stock Optimizer to Unity Catalog")
    parser.add_argument("--catalog", default="main", help="Unity Catalog name")
    parser.add_argument("--schema", default="stock_optimization", help="Schema name")
    parser.add_argument("--model-name", default="stock_optimizer", help="Model name")
    
    args = parser.parse_args()
    
    register_to_unity_catalog(
        catalog=args.catalog,
        schema=args.schema,
        model_name=args.model_name
    )


if __name__ == "__main__":
    main()
