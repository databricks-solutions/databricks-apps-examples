#!/usr/bin/env python3
"""
Local Model Training Script

This script trains the Stock Optimization model locally using MLflow
and registers it to a local tracking server. It uses the actual product
data from the application to generate realistic training scenarios.

Usage:
    cd mcp_app
    uv run python scripts/train_model_local.py

The model will be saved to:
    - MLflow tracking: ./mlruns (local)
    - Model artifacts: ./mlruns/<experiment_id>/<run_id>/artifacts/
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List

import numpy as np
import pandas as pd
import mlflow
import mlflow.pyfunc
from mlflow.models.signature import infer_signature

# Add the src directory to the path for imports
script_dir = Path(__file__).parent
src_dir = script_dir.parent / "src"
sys.path.insert(0, str(src_dir))

# Import the sample data
from range_optimizer.backend.sample_data import INITIAL_DATA


# ============================================================
# Configuration
# ============================================================

@dataclass
class OptimizationConfig:
    """Configuration parameters for stock optimization"""
    holding_cost_rate: float = 0.25  # 25% annual holding cost
    ordering_cost: float = 50.0  # Fixed cost per order
    lead_time_days: int = 7  # Lead time for restocking
    service_level: float = 0.95  # Target service level (95%)
    safety_factor: float = 1.65  # Z-score for 95% service level
    max_storage_capacity: int = 10000  # Maximum units that can be stored


# ============================================================
# MLflow PyFunc Model
# ============================================================

class StockOptimizerModel(mlflow.pyfunc.PythonModel):
    """
    MLflow pyfunc model for stock optimization using Economic Order Quantity (EOQ).
    
    This model takes forecast data and returns optimal inventory parameters including:
    - Optimal order quantity
    - Safety stock levels
    - Reorder points
    - Expected costs and profits
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
    
    def load_context(self, context):
        """Load model artifacts - in this case, the configuration"""
        config_path = context.artifacts.get("config")
        if config_path:
            with open(config_path, "r") as f:
                config_dict = json.load(f)
                self.config = OptimizationConfig(**config_dict)
        else:
            self.config = OptimizationConfig()
    
    def calculate_eoq(
        self, 
        annual_demand: float, 
        ordering_cost: float,
        unit_cost: float, 
        holding_cost_rate: float
    ) -> float:
        """
        Calculate Economic Order Quantity.
        
        EOQ = sqrt((2 * D * S) / (H * C))
        where:
            D = Annual demand
            S = Ordering cost
            H = Holding cost rate
            C = Unit cost
        """
        if annual_demand <= 0 or unit_cost <= 0:
            return 0.0
        
        eoq = np.sqrt(
            (2 * annual_demand * ordering_cost) /
            (holding_cost_rate * unit_cost)
        )
        return eoq
    
    def calculate_safety_stock(
        self, 
        demand_std: float,
        lead_time_days: int,
        safety_factor: float
    ) -> float:
        """
        Calculate safety stock based on demand variability and lead time.
        
        Safety Stock = Z * σ * sqrt(L)
        """
        if demand_std <= 0:
            return 0.0
        
        safety_stock = safety_factor * demand_std * np.sqrt(lead_time_days)
        return safety_stock
    
    def calculate_reorder_point(
        self, 
        avg_daily_demand: float,
        lead_time_days: int,
        safety_stock: float
    ) -> float:
        """
        Calculate reorder point.
        
        ROP = (Average Daily Demand × Lead Time) + Safety Stock
        """
        return (avg_daily_demand * lead_time_days) + safety_stock
    
    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize inventory levels for all products.
        
        Expected input columns:
        - SELL_ID: Product identifier
        - PRODUCT_NAME: Product name
        - AVG_DAILY_DEMAND: Average daily demand
        - DEMAND_STD: Standard deviation of demand
        - UNIT_COST: Cost per unit
        - SELLING_PRICE: Selling price per unit
        
        Returns DataFrame with optimization results.
        """
        results = []
        
        for _, row in model_input.iterrows():
            # Extract values with defaults
            sell_id = row.get('SELL_ID', 'UNKNOWN')
            product_name = row.get('PRODUCT_NAME', 'Unknown Product')
            avg_daily_demand = float(row.get('AVG_DAILY_DEMAND', 0))
            demand_std = float(row.get('DEMAND_STD', avg_daily_demand * 0.2))
            unit_cost = float(row.get('UNIT_COST', 10.0))
            selling_price = float(row.get('SELLING_PRICE', unit_cost * 2))
            
            # Convert to annual demand
            annual_demand = avg_daily_demand * 365
            
            # Calculate EOQ
            eoq = self.calculate_eoq(
                annual_demand=annual_demand,
                ordering_cost=self.config.ordering_cost,
                unit_cost=unit_cost,
                holding_cost_rate=self.config.holding_cost_rate
            )
            
            # Calculate safety stock
            safety_stock = self.calculate_safety_stock(
                demand_std=demand_std,
                lead_time_days=self.config.lead_time_days,
                safety_factor=self.config.safety_factor
            )
            
            # Calculate reorder point
            reorder_point = self.calculate_reorder_point(
                avg_daily_demand=avg_daily_demand,
                lead_time_days=self.config.lead_time_days,
                safety_stock=safety_stock
            )
            
            # Calculate optimal order quantity (considering capacity constraint)
            optimal_order_qty = min(eoq, self.config.max_storage_capacity)
            
            # Calculate maximum stock level
            max_stock_level = optimal_order_qty + safety_stock
            
            # Calculate expected costs
            avg_inventory = optimal_order_qty / 2 + safety_stock
            annual_holding_cost = avg_inventory * unit_cost * self.config.holding_cost_rate
            annual_ordering_cost = (annual_demand / optimal_order_qty) * self.config.ordering_cost if optimal_order_qty > 0 else 0
            total_annual_cost = annual_holding_cost + annual_ordering_cost
            
            # Calculate expected revenue and profit
            expected_annual_revenue = annual_demand * selling_price
            expected_annual_profit = expected_annual_revenue - (annual_demand * unit_cost) - total_annual_cost
            
            # Calculate turnover rate
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

def generate_forecast_from_products(products: List[Dict]) -> pd.DataFrame:
    """
    Generate realistic forecast data from product data.
    
    Uses shelf space, category, and other attributes to derive demand patterns.
    """
    np.random.seed(42)
    
    # Category-based demand multipliers (units per day per cm of shelf space)
    category_demand_multipliers = {
        'Beer & Seltzer': 8.0,     # High volume, frequent purchases
        'Hot Sauce': 2.5,          # Lower volume, specialty items
        'Ice Cream': 5.0,          # Medium-high volume, impulse buys
    }
    
    # Subcategory variance multipliers
    subcategory_variance = {
        'Craft Beer': 0.35,        # Higher variance (niche audience)
        'Hard Seltzer': 0.25,      # Medium variance (trending)
        'Asian Style': 0.20,       # Lower variance (staple)
        'Louisiana Style': 0.15,   # Low variance (classic)
        'Mexican Style': 0.20,     # Low-medium variance
        'Extreme Heat': 0.50,      # High variance (niche)
        'Craft/Artisan': 0.40,     # High variance (specialty)
        'Premium Pints': 0.30,     # Medium-high variance
        'Premium Tubs': 0.25,      # Medium variance
        'Low-Cal Pints': 0.35,     # Higher variance (health trend)
        'Sticks/Bars': 0.20,       # Lower variance (consistent)
    }
    
    # Price tiers based on loyalty group
    price_tiers = {
        'Premium': {'unit_cost': 12.0, 'margin': 0.45},
        'Core': {'unit_cost': 8.0, 'margin': 0.35},
        'Niche': {'unit_cost': 15.0, 'margin': 0.55},
    }
    
    forecast_data = []
    
    for product in products:
        sell_id = product['SELL_ID']
        product_name = product['PRODUCT_NAME']
        shelf_space = product['SHELF_SPACE_CM']
        category = product['CATEGORY_NAME']
        subcategory = product['SUBCATEGORY_NAME']
        loyalty_group = product['LOYALTY_GROUP']
        
        # Calculate base daily demand from shelf space and category
        demand_multiplier = category_demand_multipliers.get(category, 3.0)
        base_demand = shelf_space * demand_multiplier
        
        # Add some random variation
        base_demand *= np.random.uniform(0.8, 1.2)
        
        # Calculate demand standard deviation
        variance_multiplier = subcategory_variance.get(subcategory, 0.25)
        demand_std = base_demand * variance_multiplier
        
        # Get pricing based on loyalty tier
        pricing = price_tiers.get(loyalty_group, price_tiers['Core'])
        unit_cost = pricing['unit_cost'] * np.random.uniform(0.9, 1.1)
        selling_price = unit_cost * (1 + pricing['margin'])
        
        forecast_data.append({
            'SELL_ID': sell_id,
            'PRODUCT_NAME': product_name,
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
# Training Functions
# ============================================================

def train_and_log_model(
    forecast_df: pd.DataFrame,
    config: OptimizationConfig,
    experiment_name: str = "stock_optimization_local"
) -> str:
    """
    Train the model and log it to MLflow.
    
    Returns the run_id of the logged model.
    """
    # Set up MLflow
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment(experiment_name)
    
    print(f"\n{'='*60}")
    print("STOCK OPTIMIZATION MODEL TRAINING")
    print(f"{'='*60}")
    print(f"Experiment: {experiment_name}")
    print(f"Products: {len(forecast_df)}")
    
    # Create model instance
    model = StockOptimizerModel(config=config)
    
    # Run inference to get output for signature
    print("\n→ Running model inference for signature...")
    sample_output = model.predict(None, forecast_df)
    
    # Infer signature
    signature = infer_signature(forecast_df, sample_output)
    print("✓ Signature inferred")
    
    # Create temporary directory for artifacts
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save configuration as artifact
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump(asdict(config), f, indent=2)
        
        artifacts = {"config": config_path}
        
        # Start MLflow run
        with mlflow.start_run(run_name="stock_optimizer_training") as run:
            run_id = run.info.run_id
            print(f"\n→ MLflow Run ID: {run_id}")
            
            # Log parameters
            print("→ Logging parameters...")
            mlflow.log_param("holding_cost_rate", config.holding_cost_rate)
            mlflow.log_param("ordering_cost", config.ordering_cost)
            mlflow.log_param("lead_time_days", config.lead_time_days)
            mlflow.log_param("service_level", config.service_level)
            mlflow.log_param("safety_factor", config.safety_factor)
            mlflow.log_param("max_storage_capacity", config.max_storage_capacity)
            mlflow.log_param("num_products", len(forecast_df))
            
            # Log metrics
            print("→ Logging metrics...")
            mlflow.log_metric("total_products", len(sample_output))
            mlflow.log_metric("avg_optimal_order_qty", sample_output['OPTIMAL_ORDER_QTY'].mean())
            mlflow.log_metric("total_optimal_order_qty", sample_output['OPTIMAL_ORDER_QTY'].sum())
            mlflow.log_metric("avg_safety_stock", sample_output['SAFETY_STOCK'].mean())
            mlflow.log_metric("total_annual_cost", sample_output['TOTAL_ANNUAL_COST'].sum())
            mlflow.log_metric("total_annual_profit", sample_output['EXPECTED_ANNUAL_PROFIT'].sum())
            mlflow.log_metric("avg_turnover_rate", sample_output['TURNOVER_RATE'].mean())
            
            # Log by category
            for category in forecast_df['CATEGORY_NAME'].unique():
                cat_mask = forecast_df['SELL_ID'].isin(
                    sample_output[sample_output['SELL_ID'].isin(
                        forecast_df[forecast_df['CATEGORY_NAME'] == category]['SELL_ID']
                    )]['SELL_ID']
                )
                cat_data = sample_output[sample_output['SELL_ID'].isin(
                    forecast_df[forecast_df['CATEGORY_NAME'] == category]['SELL_ID']
                )]
                if not cat_data.empty:
                    cat_key = category.lower().replace(' ', '_').replace('&', 'and')
                    mlflow.log_metric(f"{cat_key}_total_cost", cat_data['TOTAL_ANNUAL_COST'].sum())
                    mlflow.log_metric(f"{cat_key}_total_profit", cat_data['EXPECTED_ANNUAL_PROFIT'].sum())
            
            # Log input data as artifact
            print("→ Logging input data artifact...")
            input_data_path = os.path.join(tmpdir, "training_data.csv")
            forecast_df.to_csv(input_data_path, index=False)
            mlflow.log_artifact(input_data_path)
            
            # Log output results as artifact
            output_data_path = os.path.join(tmpdir, "optimization_results.csv")
            sample_output.to_csv(output_data_path, index=False)
            mlflow.log_artifact(output_data_path)
            
            # Log the model
            print("→ Logging model...")
            model_info = mlflow.pyfunc.log_model(
                artifact_path="stock_optimizer",
                python_model=StockOptimizerModel(config=config),
                artifacts=artifacts,
                signature=signature,
                input_example=forecast_df.head(3),
                pip_requirements=["numpy", "pandas"],
            )
            
            print(f"✓ Model logged: {model_info.model_uri}")
            
            return run_id


def test_model(run_id: str, test_data: pd.DataFrame) -> pd.DataFrame:
    """
    Load and test the trained model.
    """
    print(f"\n{'='*60}")
    print("MODEL TESTING")
    print(f"{'='*60}")
    
    # Load the model
    model_uri = f"runs:/{run_id}/stock_optimizer"
    print(f"→ Loading model from: {model_uri}")
    
    loaded_model = mlflow.pyfunc.load_model(model_uri)
    print("✓ Model loaded successfully")
    
    # Run predictions
    print(f"→ Running predictions on {len(test_data)} products...")
    predictions = loaded_model.predict(test_data)
    print("✓ Predictions complete")
    
    return predictions


def print_results_summary(forecast_df: pd.DataFrame, results_df: pd.DataFrame):
    """Print a summary of the optimization results."""
    print(f"\n{'='*60}")
    print("OPTIMIZATION RESULTS SUMMARY")
    print(f"{'='*60}")
    
    print(f"\n📊 Overall Statistics:")
    print(f"   Products Optimized: {len(results_df)}")
    print(f"   Total Annual Cost: ${results_df['TOTAL_ANNUAL_COST'].sum():,.2f}")
    print(f"   Total Annual Revenue: ${results_df['EXPECTED_ANNUAL_REVENUE'].sum():,.2f}")
    print(f"   Total Annual Profit: ${results_df['EXPECTED_ANNUAL_PROFIT'].sum():,.2f}")
    print(f"   Average Turnover Rate: {results_df['TURNOVER_RATE'].mean():.2f}x")
    
    # By category
    print(f"\n📁 Results by Category:")
    for category in forecast_df['CATEGORY_NAME'].unique():
        cat_products = forecast_df[forecast_df['CATEGORY_NAME'] == category]['SELL_ID'].tolist()
        cat_results = results_df[results_df['SELL_ID'].isin(cat_products)]
        
        if not cat_results.empty:
            print(f"\n   {category}:")
            print(f"      Products: {len(cat_results)}")
            print(f"      Total Stock Needed: {cat_results['OPTIMAL_ORDER_QTY'].sum():,.0f} units")
            print(f"      Safety Stock: {cat_results['SAFETY_STOCK'].sum():,.0f} units")
            print(f"      Annual Cost: ${cat_results['TOTAL_ANNUAL_COST'].sum():,.2f}")
            print(f"      Annual Profit: ${cat_results['EXPECTED_ANNUAL_PROFIT'].sum():,.2f}")
    
    # Top 5 by profit
    print(f"\n🏆 Top 5 Products by Expected Profit:")
    top_profit = results_df.nlargest(5, 'EXPECTED_ANNUAL_PROFIT')
    for _, row in top_profit.iterrows():
        print(f"   • {row['PRODUCT_NAME']}: ${row['EXPECTED_ANNUAL_PROFIT']:,.2f}")
    
    # Products needing highest safety stock
    print(f"\n⚠️  Top 5 Products by Safety Stock Requirement:")
    top_safety = results_df.nlargest(5, 'SAFETY_STOCK')
    for _, row in top_safety.iterrows():
        print(f"   • {row['PRODUCT_NAME']}: {row['SAFETY_STOCK']:,.0f} units")


def main():
    """Main training function."""
    print("\n" + "="*60)
    print("🚀 STOCK OPTIMIZATION MODEL - LOCAL TRAINING")
    print("="*60)
    
    # 1. Generate forecast data from product data
    print("\n→ Generating forecast data from product catalog...")
    forecast_df = generate_forecast_from_products(INITIAL_DATA)
    print(f"✓ Generated forecasts for {len(forecast_df)} products")
    
    print("\n📦 Product Categories:")
    for category in forecast_df['CATEGORY_NAME'].unique():
        count = len(forecast_df[forecast_df['CATEGORY_NAME'] == category])
        print(f"   • {category}: {count} products")
    
    # 2. Configure the model
    config = OptimizationConfig(
        holding_cost_rate=0.25,
        ordering_cost=50.0,
        lead_time_days=7,
        service_level=0.95,
        safety_factor=1.65,
        max_storage_capacity=10000,
    )
    
    print(f"\n⚙️  Model Configuration:")
    print(f"   Holding Cost Rate: {config.holding_cost_rate*100}%")
    print(f"   Ordering Cost: ${config.ordering_cost}")
    print(f"   Lead Time: {config.lead_time_days} days")
    print(f"   Service Level: {config.service_level*100}%")
    print(f"   Safety Factor (Z): {config.safety_factor}")
    
    # 3. Train and log the model
    run_id = train_and_log_model(forecast_df, config)
    
    # 4. Test the model
    test_results = test_model(run_id, forecast_df)
    
    # 5. Print results
    print_results_summary(forecast_df, test_results)
    
    # 6. Summary
    print(f"\n{'='*60}")
    print("✅ TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"\nMLflow Run ID: {run_id}")
    print(f"Model URI: runs:/{run_id}/stock_optimizer")
    print(f"\nTo view results, run:")
    print(f"   cd mcp_app && uv run mlflow ui")
    print(f"\nThen open http://localhost:5000 in your browser")
    
    # Return the run_id for programmatic use
    return run_id


if __name__ == "__main__":
    main()
