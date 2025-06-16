"""Results page for Excel the Dash Way application.

This module defines the results page layout which allows users to view the
predicted results generated from submitted forecast runs. The page provides a
select box to choose a forecast run and an AG-Grid table to display the
predictions. Users can also download the results as a CSV file.
"""

from dash import register_page
from ..components.results import render_results_grid

register_page(__name__, path="/results", name="Results", title="Excel the Dash Way - Results")

layout = render_results_grid()
