"""
Generate Architecture Diagram using the 'diagrams' library.
This produces a much cleaner, professional 'Diagrams as Code' output.
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import User
from diagrams.onprem.database import Postgresql
from diagrams.programming.framework import React
from diagrams.onprem.compute import Server
from diagrams.azure.analytics import Databricks
from diagrams.programming.language import Python

# Set output directory and filename (no extension needed)
graph_attr = {
    "fontsize": "20",
    "bgcolor": "white",
    "splines": "spline",  # Curves edges
    "pad": "0.5"
}

with Diagram("Coles Inventory Intelligence Architecture", 
             show=False, 
             filename="src/dash_dbx_writeback/assets/architecture",
             direction="LR",
             graph_attr=graph_attr):

    user = User("User")

    with Cluster("Frontend Layer"):
        # Dash App + Components
        dash_app = React("Dash App\n(React + Flask)")
        
    with Cluster("Data Layer"):
        # Lakebase
        lakebase = Postgresql("Lakebase\n(PostgreSQL)")

    with Cluster("AI & Machine Learning Layer"):
        mcp = Python("MCP Server\n(Context Protocol)")
        
        with Cluster("Model Serving"):
            # Using Databricks icon for model serving endpoints
            llm = Databricks("LLM Endpoint\n(Llama 3 70B)")
            ml = Databricks("Stock Optimizer\n(Custom Model)")

    # Connections
    # User to App
    user >> Edge(label="Interacts", color="#1A73E8") >> dash_app

    # App to Data
    dash_app >> Edge(label="Read/Write", color="#00A972") >> lakebase
    lakebase >> Edge(color="#00A972") >> dash_app

    # App to MCP
    dash_app >> Edge(label="Request Insights", color="#1A73E8") >> mcp

    # App to ML (Optimization)
    dash_app >> Edge(label="Run Optimization", color="#1A73E8") >> ml

    # MCP to Data (Context)
    mcp >> Edge(label="Context", color="#1A73E8", style="dashed") >> lakebase
    
    # MCP to Models (Tool Use)
    mcp >> Edge(label="Tool Use", color="#1A73E8") >> llm
    mcp >> Edge(label="Tool Use", color="#1A73E8") >> ml

