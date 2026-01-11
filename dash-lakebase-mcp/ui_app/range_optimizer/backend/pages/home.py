import dash
from dash import html
from range_optimizer.backend.components.input import render_input_grid

# Register this page as the home page
dash.register_page(
    __name__, 
    path="/", 
    name="Range Optimizer", 
    title="Lakebase Range Optimizer - SKU Input"
)

# The layout is the SKU input grid for range optimization
layout = render_input_grid()
