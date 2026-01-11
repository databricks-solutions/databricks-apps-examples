"""
FastAPI Backend API for Range Optimizer MCP Server.

Serves:
- REST API at /api for validation, optimization, and data operations
- MCP server endpoints for AI tooling
- No Dash UI (UI is in separate ui_app)

This app has elevated database permissions for:
- Running optimization models
- AI-powered analysis
- Database schema operations
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import conf
from .router import api
from .logger import logger
from .database import initialize_connection_pool, close_all_connections
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    logger.info(f"Starting {conf.app_name} MCP Server")
    logger.info(f"Configuration:\n{conf.model_dump_json(indent=2)}")
    
    # Initialize database connection pool
    if not initialize_connection_pool():
        logger.warning("Database connection pool not initialized - some features may not work")
    else:
        logger.info("✓ Database connection pool initialized")
    
    logger.info("✓ MCP Server ready")
    logger.info(f"  - API available at: {conf.api_prefix}")
    logger.info(f"  - Docs available at: /docs")
    
    yield  # Application runs here
    
    # Shutdown
    close_all_connections()
    logger.info("MCP Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=f"{conf.app_name} MCP Server",
    description="Backend API server with elevated permissions for optimization and AI operations",
    version="1.0.0",
    lifespan=lifespan,
    # Allow OpenAPI docs to be accessed
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware to allow UI app to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the UI app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add authentication logging middleware
@app.middleware("http")
async def log_auth_requests(request: Request, call_next):
    """
    Log authentication information for API requests.
    Databricks Apps automatically validates OAuth tokens at the platform level.
    """
    # Skip auth logging for public endpoints
    if request.url.path in ["/", "/health", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Log auth info for debugging
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        # Mask the token for security
        if auth_header.startswith("Bearer "):
            token_preview = auth_header[:20] + "..." + auth_header[-8:] if len(auth_header) > 28 else "***"
            logger.debug(f"✓ Request to {request.url.path} with OAuth token: {token_preview}")
        else:
            logger.debug(f"✓ Request to {request.url.path} with auth header")
    else:
        # For localhost, no auth is expected
        if "localhost" in str(request.base_url) or "127.0.0.1" in str(request.base_url):
            logger.debug(f"→ Localhost request to {request.url.path} (no auth needed)")
        else:
            logger.warning(f"⚠️ Request to {request.url.path} without auth header (may fail on Databricks Apps)")
    
    return await call_next(request)


# Include API router
app.include_router(api)


@app.get("/")
async def root():
    """Root endpoint - returns API information"""
    return {
        "name": f"{conf.app_name} MCP Server",
        "description": "Backend API for Range Optimizer with elevated permissions",
        "version": "1.0.0",
        "api_prefix": conf.api_prefix,
        "docs_url": "/docs",
        "endpoints": {
            "validation": f"{conf.api_prefix}/validate",
            "categories": f"{conf.api_prefix}/categories",
            "layout_data": f"{conf.api_prefix}/layout-data",
            "forecasts": f"{conf.api_prefix}/forecasts",
            "optimization": f"{conf.api_prefix}/forecasts/{{forecast_id}}/optimization",
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mcp-server"}
