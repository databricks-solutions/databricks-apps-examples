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
                            "About Dash Databricks Writeback",
                            order=1,
                            ta="center",
                            mb=16,
                        ),
                        html.Hr(),
                        html.Div(
                            [
                                dmc.Title("Overview", order=2, mb=12),
                                dmc.Text(
                                    [
                                        "Excel the Dash Way is a specialized tool designed for making controlled, auditable adjustments to Delta tables in Databricks. ",
                                        "It provides a secure, user-friendly interface for business users to update data without needing to write SQL or Python code. ",
                                        "Whether you need to correct data quality issues, update reference data, or make routine adjustments to your Delta tables, ",
                                        "this application ensures these changes are made safely with proper validation and tracking.",
                                    ],
                                    size="lg",
                                    mb=16,
                                ),
                                dmc.Blockquote(
                                    [
                                        "Excel the Dash Way is a multi-page application built using ",
                                        dmc.Anchor("Dash from Plotly", href="https://dash.plotly.com/", target="_blank"),
                                        ", ",
                                        dmc.Anchor("Dash Mantine Components", href="https://www.dash-mantine-components.com/", target="_blank"),
                                        ", ",
                                        dmc.Anchor("Dash AG-Grid", href="https://www.ag-grid.com/", target="_blank"),
                                        ", and the ",
                                        dmc.Anchor("Databricks Workspace Client", href="https://databricks-sdk-py.readthedocs.io/en/latest/clients/workspace.html", target="_blank"),
                                        ".",
                                    ],
                                    icon=DashIconify(icon="material-symbols:info-outline", height=24 ),
                                ),
                                dmc.Image(
                                    src="/assets/apps.png",
                                    fit="contain",
                                    h=400,
                                    style={"imageRendering": "crisp-edges"},
                                ),
                                dmc.Title("Key Features", order=2, mt=24, mb=12),
                                dbc.ListGroup(
                                    [
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Interactive Data Editing", order=5),
                                                dmc.Text(
                                                    "Modify and update your data directly through the web interface with real-time validation.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Databricks Integration", order=5),
                                                dmc.Text(
                                                    "Seamless connection with your Databricks environment for secure data operations.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("User-Friendly Interface", order=5),
                                                dmc.Text(
                                                    "Intuitive dashboard design that makes data manipulation accessible to all users.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Data Validation", order=5),
                                                dmc.Text(
                                                    "Built-in validation ensures data integrity and consistency across operations.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="mb-4",
                                ),
                                dmc.Title("Getting Started", order=2, mt=24, mb=12),
                                dmc.Text(
                                    [
                                        "To begin using the application, navigate to the main dashboard where you can view and interact with your data. ",
                                        "Make sure you have the necessary permissions and credentials configured in your Databricks environment.",
                                    ],
                                    size="md",
                                ),
                                html.Div(
                                    [
                                        dmc.Title("Support", order=2, mt=24, mb=12),
                                        dmc.Text(
                                            [
                                                "For any questions or issues, please refer to the documentation or contact your system administrator. ",
                                                "We're committed to providing a smooth and efficient data management experience.",
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
