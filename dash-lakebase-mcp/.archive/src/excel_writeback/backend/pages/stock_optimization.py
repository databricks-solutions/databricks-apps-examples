"""Stock Optimization page for Excel the Dash Way application.

This module defines the stock optimization page layout which allows users to
run inventory optimization based on forecast sales data. The page provides
visualizations of optimal stock levels, reorder points, and cost analysis.
"""

from dash import register_page
from range_optimizer.backend.components.stock_optimization import render_stock_optimization_page

register_page(
    __name__,
    path="/stock-optimization",
    name="Stock Optimization",
    title="Excel the Dash Way - Stock Optimization"
)

layout = render_stock_optimization_page()
