"""
Standalone MCP Server entry point.

This module creates a FastAPI application that serves ONLY the MCP protocol,
separate from the main Dash UI application. This provides better security
isolation and resource management.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from .mcp import create_mcp_app
from .logger import logger
from .config import conf
from .database import initialize_connection_pool, close_all_connections
from pydantic import BaseModel
import mlflow
import os
from openai import OpenAI


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    
    logger.info("Starting standalone MCP server")
    logger.info(f"Configuration:\n{conf.model_dump_json(indent=2)}")
    
    # Initialize database connection pool
    if not initialize_connection_pool():
        logger.warning("Database connection pool not initialized - some features may not work")
    
    # Enable MLflow GenAI Tracing for Foundation Models
    logger.info("Enabling MLflow GenAI tracing")
    try:
        # Using openai autolog as Databricks FM uses openai-compatible interface
        mlflow.openai.autolog()
    except Exception as e:
        logger.warning(f"Failed to enable MLflow tracing: {e}")
    
    # Get MCP app and include its routes
    mcp_http_app = create_mcp_app()
    for route in mcp_http_app.routes:
        app.routes.append(route)
    logger.info("MCP server routes included (endpoint: /mcp)")
    
    # Run MCP lifespan alongside our app
    async with mcp_http_app.lifespan(app):
        yield  # Application runs here
    
    # Shutdown
    close_all_connections()
    logger.info("MCP server shutdown complete")


# Create standalone FastAPI app for MCP only
app = FastAPI(
    title=f"{conf.app_name} - MCP Server",
    description="Model Context Protocol server for Excel Writeback with elevated privileges",
    lifespan=lifespan
)


@app.get("/", include_in_schema=False)
async def root():
    """Health check endpoint"""
    return {
        "service": "excel-writeback-mcp",
        "status": "running",
        "mcp_endpoint": "/mcp"
    }


@app.get("/health", include_in_schema=False)
async def health():
    """Health check for monitoring"""
    return {"status": "healthy"}


class OptimizationRequest(BaseModel):
    forecast_id: str
    model_endpoint: str = "stock-optimization-model"


class InsightsRequest(BaseModel):
    forecast_id: str


class ChatRequest(BaseModel):
    forecast_id: str
    question: str
    context: str = None


@app.post("/api/run_optimization")
async def run_optimization(request: OptimizationRequest):
    """Trigger stock optimization manually"""
    from .mcp.tools import run_forecast_optimization_logic
    return run_forecast_optimization_logic(request.forecast_id, request.model_endpoint)


@app.post("/api/insights")
@mlflow.trace(name="generate_insights")
async def generate_insights(request: InsightsRequest):
    """Generate AI insights for a forecast's optimization results."""
    # Add context to trace
    mlflow.update_current_trace(tags={"context": "range optimizer", "forecast_id": request.forecast_id})
    from .database import query_df, get_workspace_client
    from .config import db_config
    
    logger.info(f"Generating insights for forecast: {request.forecast_id}")
    
    try:
        # 1. Fetch optimization results
        table = db_config.get_full_table_name("stock_optimization_results")
        query = f"SELECT * FROM {table} WHERE forecast_id = %s"
        df = query_df(query, (request.forecast_id,))
        
        if df.empty:
            return {
                "forecast_id": request.forecast_id,
                "insights": "No optimization results found for this forecast.",
                "source": "error",
                "tools_used": []
            }
        
        # 2. Convert numeric columns (they may be stored as strings)
        import pandas as pd
        numeric_cols = ["total_annual_cost", "expected_annual_profit", "service_level", "optimal_order_qty"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # 3. Calculate summary statistics
        total_products = len(df)
        total_cost = df["total_annual_cost"].sum() if "total_annual_cost" in df.columns else 0
        total_profit = df["expected_annual_profit"].sum() if "expected_annual_profit" in df.columns else 0
        avg_service_level = df["service_level"].mean() if "service_level" in df.columns else 0
        total_stock = df["optimal_order_qty"].sum() if "optimal_order_qty" in df.columns else 0
        
        # Get top and bottom performers
        if "expected_annual_profit" in df.columns and len(df) > 0:
            top_products = df.nlargest(3, "expected_annual_profit")["product_name"].tolist()
            bottom_products = df.nsmallest(3, "expected_annual_profit")["product_name"].tolist()
        else:
            top_products = []
            bottom_products = []
        
        # 3. Generate insights using LLM
        w = get_workspace_client()
        
        # Robust credential handling for OpenAI client
        # w.config.authenticate() handles all auth providers and returns the bearer token
        token_headers = w.config.authenticate()
        api_key = token_headers.get("Authorization", "").replace("Bearer ", "")
        host = w.config.host
        
        if not api_key:
             logger.warning("No Databricks token could be retrieved from WorkspaceClient")
        
        # Configure OpenAI client for Databricks
        client = OpenAI(
            api_key=api_key,
            base_url=f"{host.rstrip('/')}/serving-endpoints"
        )
        
        prompt = f"""Analyze this stock optimization summary and provide 3-4 key business insights:

Forecast ID: {request.forecast_id}
Total Products: {total_products}
Total Optimal Stock: {total_stock:.0f} units
Total Annual Cost: ${total_cost:,.2f}
Total Annual Profit: ${total_profit:,.2f}
Average Service Level: {avg_service_level:.1%}
Top Performing Products: {', '.join(top_products[:3])}
Lowest Performing Products: {', '.join(bottom_products[:3])}

Provide concise, actionable insights focusing on profitability, inventory efficiency, and recommendations.
Format as bullet points. Keep each insight to 1-2 sentences."""

        try:
            response = client.chat.completions.create(
                model="databricks-meta-llama-3-3-70b-instruct",
                messages=[
                    {"role": "system", "content": "You are an inventory optimization assistant. Provide clear, actionable business insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            
            insights = response.choices[0].message.content
            logger.info(f"Generated insights: {len(insights)} chars")
            
            return {
                "forecast_id": request.forecast_id,
                "insights": insights,
                "source": "mcp-server",
                "tools_used": ["get_optimization_results", "llm_analysis"]
            }
            
        except Exception as llm_err:
            logger.warning(f"LLM call failed, using fallback: {llm_err}")
            
            # Fallback to statistical insights
            insights = f"""• **Profit Potential**: Total annual profit opportunity is ${total_profit:,.2f} across {total_products} products.
• **Inventory Investment**: Recommended stock of {total_stock:,.0f} units with ${total_cost:,.2f} annual holding cost.
• **Service Level**: Average {avg_service_level:.1%} service level ensures high customer satisfaction.
• **Top Performers**: Focus on {', '.join(top_products[:2])} for highest returns."""
            
            return {
                "forecast_id": request.forecast_id,
                "insights": insights,
                "source": "fallback",
                "tools_used": ["get_optimization_results"]
            }
            
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return {
            "forecast_id": request.forecast_id,
            "insights": f"Error generating insights: {str(e)}",
            "source": "error",
            "error": str(e),
            "tools_used": []
        }


@app.post("/api/chat")
@mlflow.trace(name="chat_assistant")
async def chat(request: ChatRequest):
    """Handle chat messages with AI responses using optimization data."""
    # Add context to trace
    mlflow.update_current_trace(tags={"context": "range optimizer", "forecast_id": request.forecast_id})
    from .database import query_df, get_workspace_client
    from .config import db_config
    
    logger.info(f"Chat request for forecast: {request.forecast_id}")
    logger.info(f"Question: {request.question[:100]}...")
    
    try:
        # 1. Fetch relevant optimization data
        table = db_config.get_full_table_name("stock_optimization_results")
        query = f"SELECT * FROM {table} WHERE forecast_id = %s"
        df = query_df(query, (request.forecast_id,))
        
        if df.empty:
            return {
                "forecast_id": request.forecast_id,
                "question": request.question,
                "answer": "No optimization data found for this forecast. Please run the optimization first.",
                "source": "error",
                "tools_used": []
            }
        
        # 2. Convert numeric columns (they may be stored as strings)
        import pandas as pd
        numeric_cols = ["total_annual_cost", "expected_annual_profit", "expected_annual_revenue", "service_level", "optimal_order_qty"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # 3. Build context from data
        summary = {
            "total_products": len(df),
            "total_cost": df["total_annual_cost"].sum() if "total_annual_cost" in df.columns else 0,
            "total_profit": df["expected_annual_profit"].sum() if "expected_annual_profit" in df.columns else 0,
            "total_revenue": df["expected_annual_revenue"].sum() if "expected_annual_revenue" in df.columns else 0,
            "avg_service_level": df["service_level"].mean() if "service_level" in df.columns else 0,
            "total_stock": df["optimal_order_qty"].sum() if "optimal_order_qty" in df.columns else 0,
        }
        
        # Get category breakdown
        if "category_name" in df.columns:
            categories = df.groupby("category_name").agg({
                "expected_annual_profit": "sum",
                "optimal_order_qty": "sum",
                "product_name": "count"
            }).to_dict()
        else:
            categories = {}
        
        # 3. Call LLM with context
        w = get_workspace_client()
        
        # Robust credential handling for OpenAI client
        # w.config.authenticate() handles all auth providers and returns the bearer token
        token_headers = w.config.authenticate()
        api_key = token_headers.get("Authorization", "").replace("Bearer ", "")
        host = w.config.host
        
        if not api_key:
             logger.warning("No Databricks token could be retrieved from WorkspaceClient")
        
        # Configure OpenAI client for Databricks
        client = OpenAI(
            api_key=api_key,
            base_url=f"{host.rstrip('/')}/serving-endpoints"
        )
        
        data_context = f"""You have access to stock optimization results for forecast {request.forecast_id}:

Summary:
- Total Products: {summary['total_products']}
- Total Optimal Stock: {summary['total_stock']:.0f} units  
- Total Annual Cost: ${summary['total_cost']:,.2f}
- Total Annual Revenue: ${summary['total_revenue']:,.2f}
- Total Annual Profit: ${summary['total_profit']:,.2f}
- Average Service Level: {summary['avg_service_level']:.1%}

{f"Previous context: {request.context}" if request.context else ""}

Product-level data is available for detailed queries."""

        try:
            response = client.chat.completions.create(
                model="databricks-meta-llama-3-3-70b-instruct",
                messages=[
                    {"role": "system", "content": f"You are an inventory optimization assistant. Answer questions based on this data:\n{data_context}"},
                    {"role": "user", "content": request.question}
                ],
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            logger.info(f"Generated answer: {len(answer)} chars")
            
            return {
                "forecast_id": request.forecast_id,
                "question": request.question,
                "answer": answer,
                "source": "mcp-server",
                "tools_used": ["get_optimization_results", "llm_chat"]
            }
            
        except Exception as llm_err:
            logger.warning(f"LLM call failed: {llm_err}")
            
            # Fallback response
            return {
                "forecast_id": request.forecast_id,
                "question": request.question,
                "answer": f"I'm having trouble connecting to the AI service. Here's what I know about this forecast:\n\n• {summary['total_products']} products optimized\n• ${summary['total_profit']:,.2f} potential annual profit\n• {summary['total_stock']:.0f} units optimal stock\n\nPlease try again or ask a more specific question.",
                "source": "fallback",
                "tools_used": ["get_optimization_results"]
            }
            
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return {
            "forecast_id": request.forecast_id,
            "question": request.question,
            "answer": f"Error processing your question: {str(e)}",
            "source": "error",
            "error": str(e),
            "tools_used": []
        }
