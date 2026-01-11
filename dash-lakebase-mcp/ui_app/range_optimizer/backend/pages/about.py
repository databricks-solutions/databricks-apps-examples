"""About page for the Dash Databricks Writeback application.

This module defines the about page layout which provides information about the application,
its purpose, and the technologies used. The page is built using Dash Mantine Components
for a modern, responsive design.

The page includes:
- Application overview and purpose
- Key features and capabilities
- Technology stack information
- Support information

The layout is registered as a Dash page with the path '/about' and name 'About'.
"""


# Third-party imports
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import dcc
from dash import html
from dash import register_page
from dash_iconify import DashIconify


register_page(__name__, path="/about", name="About")

layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        dmc.Title(
                            "About Lakebase Inventory Intelligence",
                            order=1,
                            ta="center",
                            mb=16,
                            c="#E21837",
                        ),
                        html.Hr(),
                        html.Div(
                            [
                                dmc.Title("Overview", order=2, mb=12),
                                dmc.Text(
                                    [
                                        "Lakebase Inventory Intelligence is a purpose-built forecasting and stock optimization platform designed for modern retail operations. ",
                                        "This system combines intuitive data management with ML-powered Economic Order Quantity (EOQ) optimization to help stores and distribution centers ",
                                        "maximize profitability while minimizing holding costs. Submit category-based forecast runs and automatically generate optimal stock levels, ",
                                        "reorder points, and safety stock recommendations for every product across Beverages, Dairy, Bakery, Snacks, and Frozen categories.",
                                    ],
                                    size="lg",
                                    mb=16,
                                ),
                                dmc.Blockquote(
                                    [
                                        "Built on Databricks infrastructure with enterprise-grade security and performance. ",
                                        "This platform leverages ",
                                        dmc.Anchor("Dash from Plotly", href="https://dash.plotly.com/", target="_blank"),
                                        ", ",
                                        dmc.Anchor("Dash Mantine Components", href="https://www.dash-mantine-components.com/", target="_blank"),
                                        ", ",
                                        dmc.Anchor("Dash AG-Grid", href="https://www.ag-grid.com/", target="_blank"),
                                        ", and ",
                                        dmc.Anchor("Databricks Lakebase", href="https://docs.databricks.com/en/sql/lakebase.html", target="_blank"),
                                        " for secure, scalable inventory management.",
                                    ],
                                    icon=DashIconify(icon="material-symbols:info-outline", height=24 ),
                                    color="red",
                                ),
                                dmc.Title("System Architecture", order=2, mt=24, mb=12, c="#1A73E8"),
                                dmc.Text(
                                    "End-to-end data flow showing how forecast submissions trigger ML optimization and deliver actionable stock recommendations:",
                                    size="md",
                                    c="dimmed",
                                    mb=16,
                                ),
                                dmc.Paper(
                                    children=[
                                        html.Div(
                                            dmc.Image(
                                                src="/assets/architecture.png",
                                                fit="contain",
                                                style={"maxHeight": "70vh"},
                                            ),
                                            style={
                                                "overflowX": "auto",
                                                "display": "flex",
                                                "justifyContent": "center",
                                            },
                                        ),
                                    ],
                                    shadow="sm",
                                    p="md",
                                    radius="md",
                                    withBorder=True,
                                    style={"backgroundColor": "#FAFAFA"},
                                ),
                                dmc.Title("Key Features", order=2, mt=24, mb=12),
                                dbc.ListGroup(
                                    [
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Interactive Forecast Management", order=5),
                                                dmc.Text(
                                                    "Submit forecast runs by category with an Excel-like interface. Real-time validation ensures data quality before submission.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("ML-Powered Stock Optimization", order=5),
                                                dmc.Text(
                                                    "Automatic EOQ-based optimization calculates optimal order quantities, safety stock, reorder points, and profit projections for every product.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Databricks Lakebase Integration", order=5),
                                                dmc.Text(
                                                    "Seamless PostgreSQL connection with OAuth authentication, storing forecast submissions and optimization results in Databricks.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Comprehensive Visualization", order=5),
                                                dmc.Text(
                                                    "Interactive charts and summary cards show stock levels, turnover rates, cost vs revenue analysis, and profitability metrics.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Hybrid ML Architecture", order=5),
                                                dmc.Text(
                                                    "Optimization runs via MLflow Model Serving endpoints in Databricks with intelligent fallback for development environments.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="mb-4",
                                ),
                                dmc.Title("How It Works", order=2, mt=24, mb=12),
                                dmc.Text(
                                    [
                                        "1. Navigate to the Input page and select a product category (Beverages, Dairy, Bakery, Snacks, or Frozen). ",
                                        "2. View and edit product data in the Excel-like grid interface. Built-in validation checks for required fields and duplicates. ",
                                        "3. Submit your forecast run - the system automatically triggers stock optimization using the EOQ model. ",
                                        "4. View results in the Stock Optimization page - select your forecast run to see detailed inventory recommendations, ",
                                        "profitability analysis, and interactive visualizations. ",
                                        "5. Export results to CSV for further analysis or integration with other systems.",
                                    ],
                                    size="md",
                                ),
                                html.Div(
                                    [
                                        dmc.Title("Technology Stack", order=2, mt=24, mb=12),
                                        dmc.Text(
                                            [
                                                "Built with Dash Plotly, Dash Mantine Components, and Dash AG-Grid for a modern, responsive interface. ",
                                                "Backend powered by Databricks Lakebase PostgreSQL with connection pooling and OAuth authentication. ",
                                                "ML models deployed via MLflow Model Serving for production-grade inference. ",
                                                "The EOQ optimization algorithm considers demand variability, ordering costs, holding costs, and service level requirements ",
                                                "to provide comprehensive inventory recommendations.",
                                            ],
                                            size="md",
                                        ),
                                    ],
                                    className="mt-4",
                                ),
                            ]
                        ),
                    ],
                    width=10,
                    className="mx-auto",
                )
            ],
            className="py-4",
        )
    ],
    fluid=True,
    className="py-4",
)
