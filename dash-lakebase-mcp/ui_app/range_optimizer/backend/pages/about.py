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
                                        "Lakebase Inventory Intelligence is an AI-powered forecasting and stock optimization platform that combines the best of Databricks. ",
                                        "This system leverages a Custom MCP (Model Context Protocol) Server, Agentic AI powered by Claude Sonnet 4.5, MLflow Model Serving, ",
                                        "and Unity Catalog to deliver real-time inventory optimization. Select product ranges and receive optimized stock levels, ",
                                        "reorder points, and safety stock recommendations within seconds—powered by ML models trained on your historical data.",
                                    ],
                                    size="lg",
                                    mb=16,
                                ),
                                dmc.Blockquote(
                                    [
                                        "Built on Databricks Data Intelligence Platform with enterprise-grade security and AI capabilities. ",
                                        "This platform leverages ",
                                        dmc.Anchor("Dash from Plotly", href="https://dash.plotly.com/", target="_blank"),
                                        ", ",
                                        dmc.Anchor("Databricks Lakebase", href="https://docs.databricks.com/en/sql/lakebase.html", target="_blank"),
                                        ", ",
                                        dmc.Anchor("Unity Catalog", href="https://docs.databricks.com/en/data-governance/unity-catalog/index.html", target="_blank"),
                                        ", ",
                                        dmc.Anchor("MLflow Model Serving", href="https://docs.databricks.com/en/machine-learning/model-serving/index.html", target="_blank"),
                                        ", and ",
                                        dmc.Anchor("AI Gateway", href="https://docs.databricks.com/en/generative-ai/ai-gateway.html", target="_blank"),
                                        " with Claude Sonnet 4.5 for intelligent, agentic analysis.",
                                    ],
                                    icon=DashIconify(icon="material-symbols:info-outline", height=24 ),
                                    color="red",
                                ),
                                dmc.Title("System Architecture", order=2, mt=24, mb=12, c="#1A73E8"),
                                dmc.Text(
                                    [
                                        "The system uses a multi-layered architecture built on Databricks Data Intelligence Platform. ",
                                        "Range selections trigger ML inference via Model Serving (using Feature Store), while a Custom MCP Server ",
                                        "orchestrates agentic analysis powered by AI Gateway with Claude Sonnet 4.5. All data flows through Lakebase (PostgreSQL) ",
                                        "with results persisted to Unity Catalog Delta tables:",
                                    ],
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
                                                dmc.Title("Custom MCP Server Architecture", order=5),
                                                dmc.Text(
                                                    "Model Context Protocol (MCP) server handles all backend communication, providing secure API access to Lakebase and orchestrating ML workflows.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Agentic AI Analysis", order=5),
                                                dmc.Text(
                                                    "Agent Orchestration Framework powered by AI Gateway with Claude Sonnet 4.5 provides intelligent analysis and recommendations based on your inventory data.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("MLflow Model Serving with Feature Store", order=5),
                                                dmc.Text(
                                                    "Real-time ML inference using Databricks Model Serving endpoints with Feature Store integration for consistent, production-grade predictions.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Unity Catalog Data Governance", order=5),
                                                dmc.Text(
                                                    "All forecast results, selected ranges, optimizer results, and MLflow models are registered in Unity Catalog with full lineage and governance.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Databricks Lakebase (PostgreSQL)", order=5),
                                                dmc.Text(
                                                    "Seamless PostgreSQL connection with OAuth authentication storing all operational data and serving as the Feature Store for ML inference.",
                                                    size="md",
                                                ),
                                            ]
                                        ),
                                        dbc.ListGroupItem(
                                            [
                                                dmc.Title("Real-Time Optimization", order=5),
                                                dmc.Text(
                                                    "Select product ranges and receive optimized recommendations within seconds—full end-to-end pipeline from selection to AI-powered insights.",
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
                                        "① ", dmc.Text("Range Selected: ", fw=700, span=True), "User selects product ranges through the Dash UI interface. ",
                                        html.Br(), html.Br(),
                                        "② ", dmc.Text("Save Range to Lakebase via MCP Backend: ", fw=700, span=True), "Selection is persisted to Databricks Lakebase (PostgreSQL) through the Custom MCP Server. ",
                                        html.Br(), html.Br(),
                                        "③ ", dmc.Text("Model Serving Endpoint Does Inference: ", fw=700, span=True), "MLflow Model Serving endpoint performs real-time inference using Feature Store data from Lakebase. ",
                                        html.Br(), html.Br(),
                                        "④ ", dmc.Text("Trigger Agentic Analysis via MCP: ", fw=700, span=True), "Agent Orchestration Framework analyzes results using AI Gateway powered by Claude Sonnet 4.5. ",
                                        html.Br(), html.Br(),
                                        "⑤ ", dmc.Text("User Gets Optimized Ranges Within Seconds: ", fw=700, span=True), "AI-powered optimization results are displayed with detailed inventory recommendations, ",
                                        "profitability analysis, and interactive visualizations. All results are stored in Unity Catalog Delta tables for governance and lineage.",
                                    ],
                                    size="md",
                                ),
                                html.Div(
                                    [
                                        dmc.Title("Technology Stack", order=2, mt=24, mb=12),
                                        dmc.List(
                                            [
                                                dmc.ListItem([
                                                    dmc.Text("Frontend: ", fw=700, span=True),
                                                    "Dash Plotly, Dash Mantine Components, and Dash AG-Grid for a modern, responsive UI",
                                                ]),
                                                dmc.ListItem([
                                                    dmc.Text("Backend Integration: ", fw=700, span=True),
                                                    "Custom MCP (Model Context Protocol) Server for API orchestration and secure data access",
                                                ]),
                                                dmc.ListItem([
                                                    dmc.Text("Data Storage: ", fw=700, span=True),
                                                    "Databricks Lakebase (PostgreSQL) with OAuth authentication and connection pooling",
                                                ]),
                                                dmc.ListItem([
                                                    dmc.Text("ML Inference: ", fw=700, span=True),
                                                    "MLflow Model Serving endpoints with Feature Store integration for real-time predictions",
                                                ]),
                                                dmc.ListItem([
                                                    dmc.Text("AI & Agents: ", fw=700, span=True),
                                                    "Agent Orchestration Framework with AI Gateway powered by Claude Sonnet 4.5",
                                                ]),
                                                dmc.ListItem([
                                                    dmc.Text("Data Governance: ", fw=700, span=True),
                                                    "Unity Catalog for data lineage, model registry, and Delta table management",
                                                ]),
                                                dmc.ListItem([
                                                    dmc.Text("Platform: ", fw=700, span=True),
                                                    "Databricks Data Intelligence Platform providing enterprise-grade security, scalability, and integration",
                                                ]),
                                            ],
                                            size="md",
                                            spacing="xs",
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
