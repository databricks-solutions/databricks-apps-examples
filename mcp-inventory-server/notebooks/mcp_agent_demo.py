# Databricks notebook source
# MAGIC %md
# MAGIC # Coles Inventory Intelligence - MCP Tool-Calling Agent
# MAGIC 
# MAGIC This notebook demonstrates how to create an AI agent that uses the 
# MAGIC Coles Inventory MCP Server to query inventory data and generate insights.
# MAGIC 
# MAGIC **References:**
# MAGIC - [Databricks MCP Documentation](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
# MAGIC - [Databricks Apps Cookbook - Model Serving](https://apps-cookbook.dev/docs/dash/aiml/ml_serving_invoke)
# MAGIC - [OpenAI MCP Tool Calling Agent](https://docs.databricks.com/aws/en/notebooks/source/generative-ai/openai-mcp-tool-calling-agent.html)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Install Dependencies

# COMMAND ----------

# DBTITLE 1,Install Required Packages
%pip install -U "mcp>=1.9" "databricks-sdk[openai]>=0.60.0" "databricks-mcp" "openai>=1.0.0"
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Configuration

# COMMAND ----------

# DBTITLE 1,Configure MCP Server Connection
# MCP Server Configuration
# Replace with your deployed app URL
MCP_SERVER_URL = "https://inventory-mcp-server-7405614596482958.18.azure.databricksapps.com"

# LLM Configuration
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"

# For local development, use:
# MCP_SERVER_URL = "http://localhost:8000"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Connect to MCP Server

# COMMAND ----------

# DBTITLE 1,Create MCP Client
from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient

# Initialize Workspace Client for authentication
w = WorkspaceClient()

# Create MCP Client
# When running in a notebook, authentication is handled automatically
mcp_client = DatabricksMCPClient(server_url=MCP_SERVER_URL)

print(f"✓ Connected to MCP Server: {MCP_SERVER_URL}")

# COMMAND ----------

# DBTITLE 1,List Available Tools
# List all tools available from the MCP server
tools = mcp_client.list_tools()

print("📋 Available MCP Tools:")
print("-" * 60)
for tool in tools:
    print(f"  • {tool.name}")
    print(f"    {tool.description[:80]}...")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Test Individual Tools

# COMMAND ----------

# DBTITLE 1,Health Check
# Test the health endpoint
health_result = mcp_client.call_tool("health", {})
print("🏥 Health Check Result:")
print(health_result)

# COMMAND ----------

# DBTITLE 1,Get Forecast Runs
# Get available forecast runs
forecasts_result = mcp_client.call_tool("get_forecast_runs", {})
print("📊 Available Forecasts:")
print(f"Total: {forecasts_result.get('total_count', 0)} forecasts")

for f in forecasts_result.get('forecasts', [])[:5]:
    print(f"  • {f['forecast_id']} - {f['product_count']} products")

# COMMAND ----------

# DBTITLE 1,Get Optimization Results
# Get results for the latest forecast
if forecasts_result.get('forecasts'):
    latest_forecast_id = forecasts_result['forecasts'][0]['forecast_id']
    
    results = mcp_client.call_tool("get_optimization_results", {
        "forecast_id": latest_forecast_id
    })
    
    print(f"📈 Optimization Results for {latest_forecast_id}:")
    summary = results.get('summary', {})
    print(f"  Total Products: {summary.get('total_products', 0)}")
    print(f"  Annual Profit: ${summary.get('total_annual_profit', 0):,.2f}")
    print(f"  Avg Turnover: {summary.get('avg_turnover_rate', 0):.1f}x")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Create OpenAI-Compatible Tool-Calling Agent

# COMMAND ----------

# DBTITLE 1,Convert MCP Tools to OpenAI Function Format
def mcp_tools_to_openai_functions(mcp_tools):
    """
    Convert MCP tools to OpenAI function calling format.
    
    Based on: https://docs.databricks.com/aws/en/notebooks/source/generative-ai/openai-mcp-tool-calling-agent.html
    """
    functions = []
    for tool in mcp_tools:
        func = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema if hasattr(tool, 'input_schema') and tool.input_schema else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
        functions.append(func)
    return functions

# Convert MCP tools to OpenAI format
openai_tools = mcp_tools_to_openai_functions(tools)
print(f"✓ Converted {len(openai_tools)} tools to OpenAI format")

# COMMAND ----------

# DBTITLE 1,Define the Agent
import json
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

class InventoryAgent:
    """
    AI Agent that uses MCP tools to answer inventory questions.
    
    This agent follows the pattern from:
    https://docs.databricks.com/aws/en/notebooks/source/generative-ai/openai-mcp-tool-calling-agent.html
    """
    
    def __init__(self, mcp_client, workspace_client, llm_endpoint: str):
        self.mcp_client = mcp_client
        self.w = workspace_client
        self.llm_endpoint = llm_endpoint
        self.tools = mcp_client.list_tools()
        self.openai_tools = mcp_tools_to_openai_functions(self.tools)
        
        self.system_prompt = """You are an expert retail inventory analyst for Coles supermarkets.
You have access to tools that can query inventory forecasts, optimization results, and generate insights.

When answering questions:
1. Use the available tools to get real data
2. Provide specific numbers and actionable recommendations
3. Explain your reasoning based on the data
4. Be concise but thorough

Available data includes:
- Forecast submissions with product details
- Stock optimization results (EOQ, safety stock, reorder points)
- Financial metrics (costs, revenue, profit)
- Category and product performance insights
"""
    
    def _call_llm(self, messages: list, tools: list = None) -> dict:
        """Call the LLM endpoint with optional tool definitions."""
        response = self.w.serving_endpoints.query(
            name=self.llm_endpoint,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            temperature=0.3,
            max_tokens=1000
        )
        return response
    
    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute an MCP tool and return the result as a string."""
        print(f"  🔧 Calling tool: {tool_name}")
        result = self.mcp_client.call_tool(tool_name, arguments)
        return json.dumps(result, indent=2, default=str)
    
    def chat(self, user_message: str, max_iterations: int = 5) -> str:
        """
        Process a user message and return a response.
        
        Implements the ReAct pattern:
        1. Send message to LLM with tools
        2. If LLM requests tool calls, execute them
        3. Send tool results back to LLM
        4. Repeat until LLM provides final answer
        """
        messages = [
            ChatMessage(role=ChatMessageRole.SYSTEM, content=self.system_prompt),
            ChatMessage(role=ChatMessageRole.USER, content=user_message)
        ]
        
        print(f"\n💭 User: {user_message}")
        print("-" * 60)
        
        for iteration in range(max_iterations):
            # Call LLM
            response = self._call_llm(messages, self.openai_tools)
            
            # Check if we have a response
            if not hasattr(response, 'choices') or not response.choices:
                return "Error: No response from LLM"
            
            choice = response.choices[0]
            assistant_message = choice.message
            
            # Check for tool calls
            if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                print(f"\n  📍 Iteration {iteration + 1}: Tool calls requested")
                
                # Add assistant message to history
                messages.append(ChatMessage(
                    role=ChatMessageRole.ASSISTANT,
                    content=assistant_message.content or "",
                    tool_calls=assistant_message.tool_calls
                ))
                
                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except:
                        arguments = {}
                    
                    # Execute the tool
                    tool_result = self._execute_tool(tool_name, arguments)
                    
                    # Add tool result to messages
                    messages.append(ChatMessage(
                        role=ChatMessageRole.TOOL,
                        content=tool_result,
                        tool_call_id=tool_call.id
                    ))
            else:
                # No tool calls - we have a final answer
                final_response = assistant_message.content
                print(f"\n🤖 Agent: {final_response}")
                return final_response
        
        return "Maximum iterations reached without a final answer."

# COMMAND ----------

# DBTITLE 1,Create Agent Instance
# Create the inventory agent
agent = InventoryAgent(
    mcp_client=mcp_client,
    workspace_client=w,
    llm_endpoint=LLM_ENDPOINT
)

print("✓ Inventory Agent created and ready!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Demo: Interactive Agent Queries

# COMMAND ----------

# DBTITLE 1,Query 1: Get Available Forecasts
response = agent.chat("What forecast runs are available? List the most recent ones.")

# COMMAND ----------

# DBTITLE 1,Query 2: Restocking Recommendations
response = agent.chat("Based on the latest forecast, which products should I prioritize for restocking and why?")

# COMMAND ----------

# DBTITLE 1,Query 3: Category Analysis
response = agent.chat("Give me a detailed analysis of the Dairy category performance. What's working well and what needs improvement?")

# COMMAND ----------

# DBTITLE 1,Query 4: Compare Forecasts
response = agent.chat("Compare the two most recent forecasts. What significant changes occurred?")

# COMMAND ----------

# DBTITLE 1,Query 5: Generate AI Insights
response = agent.chat("Generate actionable insights for inventory managers based on the current optimization results. Focus on cost savings opportunities.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Custom Query
# MAGIC 
# MAGIC Enter your own question below!

# COMMAND ----------

# DBTITLE 1,Your Custom Query
# Replace with your question
custom_question = "What is the total annual profit potential across all products?"

response = agent.chat(custom_question)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Cleanup

# COMMAND ----------

# DBTITLE 1,Close MCP Client Connection
# Clean up resources
# mcp_client.close()
print("✓ Demo complete!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC 
# MAGIC This notebook demonstrated:
# MAGIC 
# MAGIC 1. **MCP Server Connection** - Connecting to the Coles Inventory MCP Server
# MAGIC 2. **Tool Discovery** - Listing available tools (data queries + ML invocation)
# MAGIC 3. **Direct Tool Calls** - Calling individual MCP tools
# MAGIC 4. **Agent Creation** - Building an OpenAI-compatible tool-calling agent
# MAGIC 5. **Interactive Queries** - Using natural language to query inventory data
# MAGIC 
# MAGIC **Key Components:**
# MAGIC - `DatabricksMCPClient` - Connects to MCP servers
# MAGIC - `WorkspaceClient` - Handles Databricks authentication
# MAGIC - `serving_endpoints.query()` - Invokes LLM with tool calling
# MAGIC 
# MAGIC **References:**
# MAGIC - [Databricks MCP Documentation](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
# MAGIC - [OpenAI MCP Tool Calling](https://docs.databricks.com/aws/en/notebooks/source/generative-ai/openai-mcp-tool-calling-agent.html)
# MAGIC - [Apps Cookbook - Model Serving](https://apps-cookbook.dev/docs/dash/aiml/ml_serving_invoke)

