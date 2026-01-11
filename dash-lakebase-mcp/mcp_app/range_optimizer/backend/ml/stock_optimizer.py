"""
Range Optimization Module

This module implements a range optimization model for retail planogram decisions.
It calculates optimal shelf facings based on demand, profitability, and constraints.

Schema Alignment:
- Primary Key: SKU_ID (e.g., "SKU3001")
- Input: SKU_ID, SKU_NAME, WEEKLY_UNITS, DEMAND_STD, UNIT_COST, UNIT_PRICE
- Output: Facings recommendations, profit metrics, change types

This module aligns with:
- Feature Store tables in Unity Catalog
- sample_data.py schema
- MLflow model signature
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class OptimizationConfig:
    """Configuration parameters for range optimization"""
    min_facings: int = 1              # Minimum facings per SKU
    max_facings: int = 6              # Maximum facings per SKU
    target_service_level: float = 0.95  # Target service level (95%)
    safety_factor: float = 1.65       # Z-score for 95% service level
    weekly_to_annual: float = 52.0    # Convert weekly to annual
    holding_cost_rate: float = 0.25   # 25% annual holding cost
    ordering_cost: float = 50.0       # $50 per order
    lead_time_days: int = 7           # 7 days to restock


def generate_dummy_forecast_data(n_products: int = 10) -> pd.DataFrame:
    """
    Generate dummy forecast data for testing.
    
    Uses the aligned schema with SKU_ID as primary key.

    Args:
        n_products: Number of products to generate forecasts for

    Returns:
        DataFrame with forecast data matching sample_data.py schema
    """
    np.random.seed(42)

    products = [
        {"SKU_ID": "SKU3001", "SKU_NAME": "Stone & Wood Pacific Ale 6pk", "BRAND": "Stone & Wood", "CATEGORY": "Beer & Seltzer", "SEGMENT": "Craft Beer", "PACK_WIDTH_MM": 180, "UNIT_PRICE": 24.00, "UNIT_COST": 14.40, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 3},
        {"SKU_ID": "SKU3003", "SKU_NAME": "Balter XPA 4pk", "BRAND": "Balter", "CATEGORY": "Beer & Seltzer", "SEGMENT": "Craft Beer", "PACK_WIDTH_MM": 150, "UNIT_PRICE": 22.00, "UNIT_COST": 13.20, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 3},
        {"SKU_ID": "SKU3009", "SKU_NAME": "White Claw Variety 12pk", "BRAND": "White Claw", "CATEGORY": "Beer & Seltzer", "SEGMENT": "Hard Seltzer", "PACK_WIDTH_MM": 260, "UNIT_PRICE": 32.00, "UNIT_COST": 17.60, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 4},
        {"SKU_ID": "SKU4001", "SKU_NAME": "Sriracha Original 455ml", "BRAND": "Sriracha", "CATEGORY": "Hot Sauce", "SEGMENT": "Asian Style", "PACK_WIDTH_MM": 80, "UNIT_PRICE": 6.50, "UNIT_COST": 2.93, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 4},
        {"SKU_ID": "SKU4003", "SKU_NAME": "Tabasco Original 150ml", "BRAND": "Tabasco", "CATEGORY": "Hot Sauce", "SEGMENT": "Louisiana Style", "PACK_WIDTH_MM": 50, "UNIT_PRICE": 5.00, "UNIT_COST": 2.25, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 3},
        {"SKU_ID": "SKU4011", "SKU_NAME": "Da Bomb Beyond Insanity 118ml", "BRAND": "Da Bomb", "CATEGORY": "Hot Sauce", "SEGMENT": "Extreme Heat", "PACK_WIDTH_MM": 45, "UNIT_PRICE": 15.00, "UNIT_COST": 7.50, "IS_MUST_STOCK": False, "CURRENT_FACINGS": 1},
        {"SKU_ID": "SKU5001", "SKU_NAME": "Ben & Jerry's Cookie Dough 458ml", "BRAND": "Ben & Jerry's", "CATEGORY": "Ice Cream", "SEGMENT": "Premium Pints", "PACK_WIDTH_MM": 110, "UNIT_PRICE": 13.50, "UNIT_COST": 6.75, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 3},
        {"SKU_ID": "SKU5004", "SKU_NAME": "Häagen-Dazs Salted Caramel 457ml", "BRAND": "Häagen-Dazs", "CATEGORY": "Ice Cream", "SEGMENT": "Premium Pints", "PACK_WIDTH_MM": 110, "UNIT_PRICE": 14.00, "UNIT_COST": 7.00, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 2},
        {"SKU_ID": "SKU5011", "SKU_NAME": "Magnum Double Caramel 4pk", "BRAND": "Magnum", "CATEGORY": "Ice Cream", "SEGMENT": "Sticks", "PACK_WIDTH_MM": 120, "UNIT_PRICE": 10.00, "UNIT_COST": 5.00, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 2},
        {"SKU_ID": "SKU5013", "SKU_NAME": "Bulla Creamy Classics Vanilla 2L", "BRAND": "Bulla", "CATEGORY": "Ice Cream", "SEGMENT": "Family Tubs", "PACK_WIDTH_MM": 180, "UNIT_PRICE": 8.00, "UNIT_COST": 4.00, "IS_MUST_STOCK": True, "CURRENT_FACINGS": 3},
    ]

    data = []
    for i, p in enumerate(products[:n_products]):
        # Generate realistic weekly demand with variability
        base_demand = np.random.randint(40, 120)
        weekly_units = base_demand * np.random.uniform(0.9, 1.1)
        demand_std = weekly_units * np.random.uniform(0.15, 0.35)

        data.append({
            **p,
            'WEEKLY_UNITS': round(weekly_units, 2),
            'DEMAND_STD': round(demand_std, 2),
            'FORECAST_4W': round(weekly_units * 4, 2),
            'IS_PRIVATE_LABEL': False,
        })

    return pd.DataFrame(data)


class StockOptimizer:
    """
    Range optimization model using Economic Order Quantity (EOQ) and facings allocation.
    
    Aligned with the MCP app schema:
    - Input columns: SKU_ID, SKU_NAME, WEEKLY_UNITS, DEMAND_STD, UNIT_COST, UNIT_PRICE, etc.
    - Output columns: RECOMMENDED_FACINGS, FACINGS_CHANGE, CHANGE_TYPE, EXPECTED_WEEKLY_PROFIT, etc.
    """

    def __init__(self, config: OptimizationConfig = None):
        """
        Initialize the range optimizer.

        Args:
            config: Configuration parameters for optimization
        """
        self.config = config or OptimizationConfig()

    def calculate_optimal_facings(
        self, 
        weekly_units: float, 
        demand_std: float, 
        margin: float, 
        is_must_stock: bool
    ) -> int:
        """
        Calculate optimal facings based on demand and profitability.
        
        Uses a space productivity approach:
        - Higher weekly profit → more facings
        - Higher volatility → more safety stock → more facings
        """
        if weekly_units <= 0 or margin <= 0:
            return self.config.min_facings if is_must_stock else 0
        
        # Weekly profit per unit
        weekly_profit = weekly_units * margin
        
        # Safety stock multiplier (higher variance = need more buffer)
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

    def optimize_inventory(self, forecast_df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize facings allocation for all SKUs based on forecast data.

        Args:
            forecast_df: DataFrame with forecast data including:
                - SKU_ID: Product identifier (primary key)
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
                - CURRENT_FACINGS: Current shelf facings

        Returns:
            DataFrame with optimization recommendations
        """
        results = []

        for _, row in forecast_df.iterrows():
            # Extract values (handle both uppercase and lowercase columns)
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

    def get_optimization_summary(self, optimized_df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics from optimization results.

        Args:
            optimized_df: DataFrame with optimization results

        Returns:
            Dictionary with summary statistics
        """
        return {
            'total_skus': len(optimized_df),
            'skus_ranged': int(optimized_df['IS_RANGED'].sum()),
            'total_facings': int(optimized_df['RECOMMENDED_FACINGS'].sum()),
            'total_weekly_profit': float(optimized_df['EXPECTED_WEEKLY_PROFIT'].sum()),
            'avg_space_productivity': float(optimized_df['SPACE_PRODUCTIVITY'].mean()),
            'service_level': self.config.target_service_level,
            # Change summary
            'skus_increased': len(optimized_df[optimized_df['CHANGE_TYPE'] == 'increased']),
            'skus_decreased': len(optimized_df[optimized_df['CHANGE_TYPE'] == 'decreased']),
            'skus_new': len(optimized_df[optimized_df['CHANGE_TYPE'] == 'new']),
            'skus_removed': len(optimized_df[optimized_df['CHANGE_TYPE'] == 'removed']),
        }
