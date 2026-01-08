"""
API Handlers for the MCP Server REST endpoints.

These handlers orchestrate MCP tools and LLM calls to provide
insights and chat functionality for the Dash app.
"""

import datetime
from typing import Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from . import utils
from . import tools as mcp_tools

def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [MCP-API] {message}")

async def run_optimization(forecast_id: str) -> dict:
    """
    Trigger the stock optimization process for a forecast via MCP tool logic.
    """
    log(f"⚡ Running optimization for forecast: {forecast_id}")
    return mcp_tools._run_forecast_optimization_impl(forecast_id)


def get_optimization_data(forecast_id: str) -> dict:
    """
    Get optimization data using database queries (simulating MCP tool call).
    """
    log(f"📊 MCP Tool: get_optimization_results({forecast_id})")
    try:
        query = """
            SELECT product_name, category_name, avg_daily_demand, optimal_order_qty, 
                   expected_annual_profit, turnover_rate
            FROM excel_app.stock_optimization_results
            WHERE forecast_id = %s
            ORDER BY expected_annual_profit DESC LIMIT 20
        """
        results = utils.execute_query(query, (forecast_id,))
        if not results: return {"error": "No results found", "data": []}
        return {
            "forecast_id": forecast_id,
            "top_products": results[:10],
            "total_products": len(results),
            "total_annual_profit": sum(r.get('expected_annual_profit', 0) or 0 for r in results)
        }
    except Exception as e:
        log(f"❌ Error getting optimization data: {e}")
        return {"error": str(e)}

def format_context_for_llm(data: dict) -> str:
    """Format optimization data as context for the LLM."""
    if "error" in data: return "No data."
    context = f"Total Profit: ${data.get('total_annual_profit', 0):,.2f}\nTop Products:\n"
    for p in data.get('top_products', []):
        context += f"- {p.get('product_name')}: Profit=${p.get('expected_annual_profit', 0):,.0f}\n"
    return context

async def generate_insights(forecast_id: str) -> dict:
    """Generate key insights for a forecast."""
    log(f"🚀 Generating insights for forecast: {forecast_id}")
    data = get_optimization_data(forecast_id)
    context = format_context_for_llm(data)
    
    try:
        w = WorkspaceClient()
        response = w.serving_endpoints.query(
            name="databricks-meta-llama-3-3-70b-instruct",
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content="Summarize inventory insights."),
                ChatMessage(role=ChatMessageRole.USER, content=f"Data:\n{context}"),
            ],
            max_tokens=300
        )
        insights = response.choices[0].message.content if hasattr(response, 'choices') else "No insights."
    except Exception as e:
        insights = f"Error generating insights: {e}"
    
    return {"forecast_id": forecast_id, "insights": insights, "source": "mcp-server"}

async def handle_chat(forecast_id: str, question: str, context: Optional[str] = None) -> dict:
    """Handle a chat message about forecast results."""
    log(f"💬 Chat request: {question}")
    data = get_optimization_data(forecast_id)
    full_context = context if context else format_context_for_llm(data)
    
    try:
        w = WorkspaceClient()
        response = w.serving_endpoints.query(
            name="databricks-meta-llama-3-3-70b-instruct",
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content="Answer user question based on data."),
                ChatMessage(role=ChatMessageRole.USER, content=f"Data:\n{full_context}\n\nQ: {question}"),
            ],
            max_tokens=300
        )
        answer = response.choices[0].message.content if hasattr(response, 'choices') else "No answer."
    except Exception as e:
        answer = f"Error: {e}"
        
    return {"forecast_id": forecast_id, "question": question, "answer": answer, "source": "mcp-server"}
