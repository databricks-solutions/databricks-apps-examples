"""Range Optimization Results page for Lakebase Range Optimizer application.

This module defines the optimization results page layout which displays
recommended planogram output from the HiGHS-based range optimizer.
Shows SKU assortment decisions, facings allocation, and profit analysis.
"""

from dash import register_page
from range_optimizer.backend.components.stock_optimization import render_stock_optimization_page

register_page(
    __name__,
    path="/stock-optimization",
    name="Planogram Results",
    title="Lakebase Range Optimizer - Planogram Results"
)

layout = render_stock_optimization_page()
