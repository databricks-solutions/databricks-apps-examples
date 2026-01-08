"""
FastAPI application configuration for the Coles Inventory MCP server.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional

from .tools import load_tools
from .utils import header_store
from . import api_handlers

# Create the FastMCP server instance
mcp_server = FastMCP(name="inventory-mcp-server")
load_tools(mcp_server)
mcp_app = mcp_server.http_app()

app = FastAPI(
    title="Coles Inventory Intelligence MCP Server",
    version="0.1.0",
    lifespan=mcp_app.lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InsightsRequest(BaseModel):
    forecast_id: str

class ChatRequest(BaseModel):
    forecast_id: str
    question: str
    context: Optional[str] = None

class OptimizationRequest(BaseModel):
    forecast_id: str

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "server": "mcp-inventory-server"}

@app.post("/api/insights")
async def generate_insights(request: InsightsRequest):
    return await api_handlers.generate_insights(request.forecast_id)

@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    return await api_handlers.handle_chat(request.forecast_id, request.question, request.context)

@app.post("/api/run_optimization")
async def run_optimization_endpoint(request: OptimizationRequest):
    """Trigger stock optimization via MCP"""
    return await api_handlers.run_optimization(request.forecast_id)

combined_app = FastAPI(
    title="Coles Inventory MCP Server",
    routes=[*mcp_app.routes, *app.routes],
    lifespan=mcp_app.lifespan,
)

@combined_app.middleware("http")
async def capture_headers(request: Request, call_next):
    header_store.set(dict(request.headers))
    return await call_next(request)
