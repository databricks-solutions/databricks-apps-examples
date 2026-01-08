"""
Example MCP Agent for Coles Inventory Intelligence.

This script demonstrates how to create an agent that uses the MCP server
to query inventory data and generate insights.

Based on:
- https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp
- https://apps-cookbook.dev/docs/dash/aiml/ml_serving_invoke

Usage:
    # Local development (MCP server running locally)
    python scripts/dev/example_agent.py --local
    
    # Against deployed MCP server
    python scripts/dev/example_agent.py --app-url https://inventory-mcp-server-*.azuredatabricksapps.com
"""

import argparse
import json
from typing import Any


def create_mcp_client(server_url: str, token: str = None):
    """
    Create an MCP client to interact with the inventory MCP server.
    
    Args:
        server_url: URL of the MCP server
        token: OAuth token for authentication (required for deployed apps)
        
    Returns:
        DatabricksMCPClient instance
    """
    try:
        from databricks_mcp import DatabricksMCPClient
        
        if token:
            return DatabricksMCPClient(server_url=server_url, token=token)
        else:
            return DatabricksMCPClient(server_url=server_url)
    except ImportError:
        print("Please install databricks-mcp: pip install databricks-mcp")
        raise


def list_available_tools(client) -> list:
    """List all available tools from the MCP server."""
    tools = client.list_tools()
    print("\n📋 Available MCP Tools:")
    print("-" * 50)
    for tool in tools:
        print(f"  • {tool.name}: {tool.description[:60]}...")
    return tools


def call_tool(client, tool_name: str, arguments: dict = None) -> Any:
    """Call an MCP tool and return the result."""
    print(f"\n🔧 Calling tool: {tool_name}")
    if arguments:
        print(f"   Arguments: {json.dumps(arguments, indent=2)}")
    
    result = client.call_tool(tool_name, arguments or {})
    return result


def demo_inventory_queries(client):
    """Demonstrate various inventory queries using MCP tools."""
    
    print("\n" + "=" * 60)
    print("🏪 COLES INVENTORY INTELLIGENCE - MCP AGENT DEMO")
    print("=" * 60)
    
    # 1. Health check
    print("\n📍 Step 1: Health Check")
    health = call_tool(client, "health")
    print(f"   Status: {health.get('status')}")
    print(f"   Database: {health.get('database')}")
    
    # 2. Get available forecast runs
    print("\n📍 Step 2: Get Available Forecasts")
    forecasts = call_tool(client, "get_forecast_runs")
    print(f"   Found {forecasts.get('total_count', 0)} forecast runs")
    
    if forecasts.get('forecasts'):
        latest_forecast = forecasts['forecasts'][0]
        forecast_id = latest_forecast['forecast_id']
        print(f"   Latest: {forecast_id} ({latest_forecast['product_count']} products)")
        
        # 3. Get optimization results
        print("\n📍 Step 3: Get Optimization Results")
        results = call_tool(client, "get_optimization_results", {"forecast_id": forecast_id})
        summary = results.get('summary', {})
        print(f"   Total Products: {summary.get('total_products', 0)}")
        print(f"   Annual Profit: ${summary.get('total_annual_profit', 0):,.2f}")
        print(f"   Avg Turnover: {summary.get('avg_turnover_rate', 0):.1f}x")
        
        # 4. Get restocking recommendations
        print("\n📍 Step 4: Restocking Recommendations")
        recommendations = call_tool(client, "recommend_restocking", {
            "forecast_id": forecast_id,
            "top_n": 3
        })
        print("   Top 3 Products to Restock:")
        for rec in recommendations.get('recommendations', [])[:3]:
            print(f"   {rec['rank']}. {rec['product_name']} - {rec['reason']}")
        
        # 5. Category insights
        print("\n📍 Step 5: Category Insights (Dairy)")
        insights = call_tool(client, "get_category_insights", {"category": "Dairy"})
        metrics = insights.get('category_metrics', {})
        print(f"   Top Performer: {metrics.get('top_performer', 'N/A')}")
        print(f"   Improvement Opportunity: {metrics.get('improvement_opportunity', 'N/A')}")
        print(f"   Total Profit: ${metrics.get('total_annual_profit', 0):,.2f}")
        
        # 6. Generate AI insights (if LLM endpoint available)
        print("\n📍 Step 6: AI-Generated Insights")
        try:
            ai_insights = call_tool(client, "generate_inventory_insights", {
                "forecast_id": forecast_id,
                "question": "What are the top 3 actionable recommendations for this inventory?"
            })
            if ai_insights.get('status') == 'success':
                print(f"   {ai_insights.get('insights', 'No insights generated')}")
            else:
                print(f"   (LLM endpoint not available: {ai_insights.get('error', 'Unknown error')})")
        except Exception as e:
            print(f"   (Skipping AI insights: {e})")
    
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETE")
    print("=" * 60)


def create_agent_with_openai(mcp_tools: list, user_query: str):
    """
    Create an agent using OpenAI-compatible API with MCP tools.
    
    This demonstrates the pattern from:
    https://docs.databricks.com/aws/en/notebooks/source/generative-ai/openai-mcp-tool-calling-agent.html
    
    Args:
        mcp_tools: List of MCP tools to make available to the agent
        user_query: The user's question
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    
    w = WorkspaceClient()
    
    # Convert MCP tools to OpenAI function format
    functions = []
    for tool in mcp_tools:
        functions.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema if hasattr(tool, 'input_schema') else {}
            }
        })
    
    # Call the LLM with tools
    response = w.serving_endpoints.query(
        name="databricks-meta-llama-3-3-70b-instruct",
        messages=[
            ChatMessage(
                role=ChatMessageRole.SYSTEM,
                content="You are an inventory analyst assistant. Use the available tools to answer questions about Coles inventory optimization."
            ),
            ChatMessage(
                role=ChatMessageRole.USER,
                content=user_query
            )
        ],
        tools=functions,
        tool_choice="auto"
    )
    
    return response


def main():
    parser = argparse.ArgumentParser(description="Coles Inventory MCP Agent Demo")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Connect to local MCP server (http://localhost:8000)"
    )
    parser.add_argument(
        "--app-url",
        type=str,
        help="URL of deployed MCP server app"
    )
    parser.add_argument(
        "--token",
        type=str,
        help="OAuth token for authentication"
    )
    args = parser.parse_args()
    
    # Determine server URL
    if args.local:
        server_url = "http://localhost:8000"
    elif args.app_url:
        server_url = args.app_url
    else:
        print("Please specify --local or --app-url")
        return
    
    print(f"🔌 Connecting to MCP server: {server_url}")
    
    try:
        # Create MCP client
        client = create_mcp_client(server_url, args.token)
        
        # List available tools
        tools = list_available_tools(client)
        
        # Run demo queries
        demo_inventory_queries(client)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

