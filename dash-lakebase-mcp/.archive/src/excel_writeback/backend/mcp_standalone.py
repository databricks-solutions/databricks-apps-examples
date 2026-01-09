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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    
    logger.info("Starting standalone MCP server")
    logger.info(f"Configuration:\n{conf.model_dump_json(indent=2)}")
    
    # Initialize database connection pool
    if not initialize_connection_pool():
        logger.warning("Database connection pool not initialized - some features may not work")
    
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
