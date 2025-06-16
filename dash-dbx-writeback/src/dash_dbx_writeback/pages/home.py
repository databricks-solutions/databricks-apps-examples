import dash
from dash import html
from ..components.input import render_input_grid

# Register this page as the home page
dash.register_page(__name__, path="/", name="Home", title="Excel the Dash Way - Home")

# The layout is the main input grid functionality
layout = render_input_grid()
