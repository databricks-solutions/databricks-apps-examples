import dash
from dash import html
from excel_writeback.backend.components.input import render_input_grid

# Register this page as the home page
dash.register_page(__name__, path="/", name="Home", title="Lakebase Inventory Intelligence - Home")

# The layout is the main input grid functionality
layout = render_input_grid()
