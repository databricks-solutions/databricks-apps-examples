"""
Stock Optimization Module

This module implements a traditional ML/optimization model for inventory management.
It uses a simple Economic Order Quantity (EOQ) based approach with safety stock
calculations to optimize inventory levels based on forecast demand.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class OptimizationConfig:
    """Configuration parameters for stock optimization"""
    holding_cost_rate: float = 0.25  # 25% annual holding cost
    ordering_cost: float = 50.0  # Fixed cost per order
    lead_time_days: int = 7  # Lead time for restocking
    service_level: float = 0.95  # Target service level (95%)
    safety_factor: float = 1.65  # Z-score for 95% service level
    max_storage_capacity: int = 10000  # Maximum units that can be stored


def generate_dummy_forecast_data(n_products: int = 10) -> pd.DataFrame:
    """
    Generate dummy forecast sales data for testing.

    Args:
        n_products: Number of products to generate forecasts for

    Returns:
        DataFrame with forecast sales data
    """
    np.random.seed(42)

    product_names = [
        "Coles Brand Milk 2L", "Woolworths Bread White", "Arnott's Tim Tams",
        "Vegemite 380g", "Kangaroo Steak", "Tim Tam Slam Kit",
        "Organic Honey 500g", "Fair Trade Coffee 250g", "Greek Yogurt 1kg",
        "Sourdough Bread", "Avocado Oil 500ml", "Quinoa 1kg"
    ]

    data = []
    for i in range(min(n_products, len(product_names))):
        # Generate realistic forecast with some variability
        base_demand = np.random.randint(50, 500)
        daily_forecast = np.random.normal(base_demand, base_demand * 0.2, 30)  # 30 days
        daily_forecast = np.maximum(daily_forecast, 0)  # No negative demand

        data.append({
            'SELL_ID': f'SELL{i+1:03d}',
            'PRODUCT_NAME': product_names[i],
            'AVG_DAILY_DEMAND': daily_forecast.mean(),
            'DEMAND_STD': daily_forecast.std(),
            'TOTAL_FORECAST_30D': daily_forecast.sum(),
            'UNIT_COST': np.random.uniform(2.0, 50.0),
            'SELLING_PRICE': np.random.uniform(5.0, 80.0),
        })

    return pd.DataFrame(data)


class StockOptimizer:
    """
    Traditional ML-based stock optimization model using Economic Order Quantity (EOQ)
    and safety stock calculations.
    """

    def __init__(self, config: OptimizationConfig = None):
        """
        Initialize the stock optimizer.

        Args:
            config: Configuration parameters for optimization
        """
        self.config = config or OptimizationConfig()

    def calculate_eoq(self, annual_demand: float, ordering_cost: float,
                     unit_cost: float, holding_cost_rate: float) -> float:
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

    def calculate_safety_stock(self, lead_time_demand: float,
                               demand_std: float,
                               lead_time_days: int,
                               safety_factor: float) -> float:
        """
        Calculate safety stock based on demand variability and lead time.

        Safety Stock = Z * σ * sqrt(L)
        where:
            Z = Safety factor (z-score for service level)
            σ = Standard deviation of demand
            L = Lead time
        """
        if demand_std <= 0:
            return 0.0

        safety_stock = safety_factor * demand_std * np.sqrt(lead_time_days)
        return safety_stock

    def calculate_reorder_point(self, avg_daily_demand: float,
                               lead_time_days: int,
                               safety_stock: float) -> float:
        """
        Calculate reorder point.

        ROP = (Average Daily Demand × Lead Time) + Safety Stock
        """
        reorder_point = (avg_daily_demand * lead_time_days) + safety_stock
        return reorder_point

    def optimize_inventory(self, forecast_df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize inventory levels for all products based on forecast data.

        Args:
            forecast_df: DataFrame with forecast data including:
                - SELL_ID: Product identifier
                - PRODUCT_NAME: Product name
                - AVG_DAILY_DEMAND: Average daily demand
                - DEMAND_STD: Standard deviation of demand
                - UNIT_COST: Cost per unit
                - SELLING_PRICE: Selling price per unit

        Returns:
            DataFrame with optimized inventory recommendations
        """
        results = []

        for _, row in forecast_df.iterrows():
            # Extract values
            sell_id = row['SELL_ID']
            product_name = row['PRODUCT_NAME']
            avg_daily_demand = row['AVG_DAILY_DEMAND']
            demand_std = row['DEMAND_STD']
            unit_cost = row['UNIT_COST']
            selling_price = row['SELLING_PRICE']

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
                lead_time_demand=avg_daily_demand * self.config.lead_time_days,
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
            annual_holding_cost = (optimal_order_qty / 2 + safety_stock) * unit_cost * self.config.holding_cost_rate
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

    def get_optimization_summary(self, optimized_df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics from optimization results.

        Args:
            optimized_df: DataFrame with optimization results

        Returns:
            Dictionary with summary statistics
        """
        return {
            'total_products': len(optimized_df),
            'total_optimal_stock_units': optimized_df['OPTIMAL_ORDER_QTY'].sum(),
            'total_safety_stock_units': optimized_df['SAFETY_STOCK'].sum(),
            'total_max_stock_units': optimized_df['MAX_STOCK_LEVEL'].sum(),
            'total_annual_cost': optimized_df['TOTAL_ANNUAL_COST'].sum(),
            'total_annual_revenue': optimized_df['EXPECTED_ANNUAL_REVENUE'].sum(),
            'total_annual_profit': optimized_df['EXPECTED_ANNUAL_PROFIT'].sum(),
            'avg_turnover_rate': optimized_df['TURNOVER_RATE'].mean(),
            'service_level': self.config.service_level,
        }
