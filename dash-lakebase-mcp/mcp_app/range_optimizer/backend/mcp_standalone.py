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


from typing import List, Optional
from fastapi import Query, HTTPException
import pandas as pd
import numpy as np


# =============================================================================
# Request/Response Models
# =============================================================================

class OptimizationRequest(BaseModel):
    forecast_id: str
    model_endpoint: str = "stock-optimization-model"


class InsightsRequest(BaseModel):
    forecast_id: str


class ChatRequest(BaseModel):
    forecast_id: str
    question: str
    context: str = None


class SKUData(BaseModel):
    """Single SKU record"""
    SKU_ID: str
    SKU_NAME: Optional[str] = None
    BRAND: Optional[str] = None
    CATEGORY: Optional[str] = None
    SEGMENT: Optional[str] = None
    PACK_SIZE: Optional[str] = None
    PACK_WIDTH_MM: Optional[int] = None
    WEEKLY_UNITS: Optional[int] = None
    UNIT_PRICE: Optional[float] = None
    UNIT_COST: Optional[float] = None
    GROSS_MARGIN_PCT: Optional[float] = None
    CURRENT_FACINGS: Optional[int] = None
    IS_PRIVATE_LABEL: Optional[bool] = False
    IS_MUST_STOCK: Optional[bool] = False
    STATUS: Optional[str] = "active"
    
    class Config:
        extra = "allow"  # Allow additional fields


class SKUBatchRequest(BaseModel):
    """Batch of SKU records for save operations"""
    records: List[SKUData]
    overwrite: bool = False


class OptimizationRunRequest(BaseModel):
    """Request to submit a new optimization run"""
    records: List[SKUData]


# =============================================================================
# SKU Data API Endpoints
# =============================================================================

@app.get("/api/skus")
async def get_skus(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: Optional[int] = Query(None, description="Limit results")
):
    """
    Get SKU data from dim_sku table.
    Used by ui_app for grid display.
    """
    from .database import query_df, check_table_exists, bulk_insert
    from .config import db_config
    from .sample_data import INITIAL_DATA
    
    table = db_config.dim_sku_table
    logger.info(f"GET /api/skus - category: {category}, limit: {limit}")
    
    try:
        # Initialize table with sample data if it doesn't exist
        if not check_table_exists(table):
            logger.info(f"Table {table} doesn't exist, initializing with sample data")
            df = pd.DataFrame(INITIAL_DATA)
            bulk_insert(table, df, overwrite=False)
        
        # Build query
        if category and category != "All":
            query = f'SELECT * FROM {table} WHERE "CATEGORY" = %s'
            params = (category,)
        else:
            query = f'SELECT * FROM {table}'
            params = None
        
        if limit:
            query += f' LIMIT {limit}'
        
        df = query_df(query, params)
        
        if df.empty:
            logger.info("No data in database, returning sample data")
            data = INITIAL_DATA
            if category and category != "All":
                data = [r for r in data if r.get("CATEGORY") == category]
            return {"skus": data, "count": len(data), "source": "sample"}
        
        records = df.to_dict("records")
        logger.info(f"Returning {len(records)} SKUs")
        return {"skus": records, "count": len(records), "source": "database"}
        
    except Exception as e:
        logger.error(f"Error fetching SKUs: {e}")
        # Fallback to sample data
        from .sample_data import INITIAL_DATA
        data = INITIAL_DATA
        if category and category != "All":
            data = [r for r in data if r.get("CATEGORY") == category]
        return {"skus": data, "count": len(data), "source": "fallback", "error": str(e)}


@app.post("/api/skus")
async def save_skus(request: SKUBatchRequest):
    """
    Save SKU data to dim_sku table.
    Used by ui_app for data persistence.
    """
    from .database import bulk_insert
    from .config import db_config
    
    table = db_config.dim_sku_table
    logger.info(f"POST /api/skus - {len(request.records)} records, overwrite: {request.overwrite}")
    
    try:
        records = [r.model_dump(exclude_none=True) for r in request.records]
        df = pd.DataFrame(records)
        
        rows = bulk_insert(table, df, overwrite=request.overwrite)
        logger.info(f"Saved {rows} SKU records")
        
        return {"success": True, "rows_affected": rows, "message": f"Saved {rows} records"}
        
    except Exception as e:
        logger.error(f"Error saving SKUs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ValidateRequest(BaseModel):
    """Request for data validation"""
    data: List[dict]


@app.post("/api/validate")
async def validate_data(request: ValidateRequest):
    """
    Validate SKU data for correctness.
    Used by ui_app to validate grid data before saving.
    """
    logger.info(f"POST /api/validate - {len(request.data)} records")
    
    issues = []
    
    # Valid values for categorical fields
    VALID_SEGMENTS_BY_CATEGORY = {
        "Beer & Seltzer": {"Craft Beer", "Hard Seltzer"},
        "Hot Sauce": {"Asian Style", "Louisiana Style", "Mexican Style"},
        "Ice Cream": {"Premium Pints", "Family Tubs"},
    }
    ALL_VALID_SEGMENTS = {"Craft Beer", "Hard Seltzer", "Asian Style", "Louisiana Style", 
                          "Mexican Style", "Premium Pints", "Family Tubs"}
    
    for i, record in enumerate(request.data):
        row_num = i + 1
        sku_id = record.get("SKU_ID", f"Row {row_num}")
        
        # Required field validation
        if not record.get("SKU_ID"):
            issues.append({"row_index": i, "sell_id": sku_id, "field": "SKU_ID", 
                          "severity": "error", "message": "SKU_ID is required"})
        
        # Numeric field validation
        numeric_fields = ["WEEKLY_UNITS", "UNIT_PRICE", "UNIT_COST", "CURRENT_FACINGS", "PACK_WIDTH_MM"]
        for field in numeric_fields:
            value = record.get(field)
            if value is not None and value != "":
                try:
                    float(value)
                except (ValueError, TypeError):
                    issues.append({"row_index": i, "sell_id": sku_id, "field": field, 
                                  "severity": "error", "message": f"{field} must be numeric"})
        
        # Check for missing required numeric fields
        required_numeric = ["WEEKLY_UNITS", "CURRENT_FACINGS"]
        for field in required_numeric:
            value = record.get(field)
            if value is None or value == "":
                issues.append({"row_index": i, "sell_id": sku_id, "field": field,
                              "severity": "error", "message": f"{field} is required"})
        
        # Business rule validation
        if record.get("UNIT_PRICE") and record.get("UNIT_COST"):
            try:
                price = float(record.get("UNIT_PRICE", 0))
                cost = float(record.get("UNIT_COST", 0))
                if cost > price:
                    issues.append({"row_index": i, "sell_id": sku_id, "field": "UNIT_COST",
                                  "severity": "warning", "message": "Cost exceeds price (negative margin)"})
            except (ValueError, TypeError):
                pass
        
        # Facings validation
        facings = record.get("CURRENT_FACINGS")
        if facings is not None and facings != "":
            try:
                if int(facings) < 0:
                    issues.append({"row_index": i, "sell_id": sku_id, "field": "CURRENT_FACINGS",
                                  "severity": "error", "message": "Facings cannot be negative"})
            except (ValueError, TypeError):
                pass
        
        # SEGMENT validation
        segment = record.get("SEGMENT")
        category = record.get("CATEGORY")
        if not segment or segment == "":
            issues.append({"row_index": i, "sell_id": sku_id, "field": "SEGMENT",
                          "severity": "error", "message": "SEGMENT is required"})
        elif segment not in ALL_VALID_SEGMENTS:
            issues.append({"row_index": i, "sell_id": sku_id, "field": "SEGMENT",
                          "severity": "error", "message": f"Invalid SEGMENT: {segment}"})
        elif category and category in VALID_SEGMENTS_BY_CATEGORY:
            valid_for_category = VALID_SEGMENTS_BY_CATEGORY[category]
            if segment not in valid_for_category:
                issues.append({"row_index": i, "sell_id": sku_id, "field": "SEGMENT",
                              "severity": "error", 
                              "message": f"SEGMENT '{segment}' not valid for CATEGORY '{category}'"})
    
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    
    has_errors = len(errors) > 0
    has_warnings = len(warnings) > 0
    valid = not has_errors
    
    if valid and not has_warnings:
        summary = f"✓ Validation passed! {len(request.data)} SKU records are ready for submission."
    elif valid and has_warnings:
        summary = f"⚠ {len(warnings)} warning(s) found. You can still submit."
    else:
        summary = f"✗ {len(errors)} error(s) found. Please fix before submitting."
    
    return {
        "valid": valid,
        "has_errors": has_errors,
        "has_warnings": has_warnings,
        "issues": issues,
        "summary": summary,
        "records_checked": len(request.data)
    }


@app.get("/api/categories")
async def get_categories():
    """
    Get list of unique categories with counts.
    Used by ui_app for category dropdown.
    """
    from .database import query_df, check_table_exists
    from .config import db_config
    
    table = db_config.dim_sku_table
    logger.info("GET /api/categories")
    
    try:
        if not check_table_exists(table):
            return {"categories": [{"name": "All", "count": 0}]}
        
        query = f'''
            SELECT "CATEGORY" as name, COUNT(*) as count
            FROM {table}
            GROUP BY "CATEGORY"
            ORDER BY "CATEGORY"
        '''
        df = query_df(query)
        
        categories = [{"name": "All", "count": df["count"].sum()}]
        categories.extend(df.to_dict("records"))
        
        return {"categories": categories}
        
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return {"categories": [{"name": "All", "count": 0}], "error": str(e)}


# =============================================================================
# Optimization Run API Endpoints
# =============================================================================

@app.get("/api/optimization-runs")
async def get_optimization_runs(limit: int = Query(20, description="Maximum runs to return")):
    """
    Get list of optimization runs with results.
    Used by ui_app results page dropdown.
    """
    from .database import query_df, check_table_exists
    from .config import db_config
    
    logger.info(f"GET /api/optimization-runs - limit: {limit}")
    
    try:
        # First try to get runs from results table
        results_table = db_config.opt_planogram_table
        if check_table_exists(results_table):
            query = f'''
                SELECT DISTINCT optimization_run_id as run_id,
                       MAX(optimization_run_date) as timestamp,
                       COUNT(*) as sku_count
                FROM {results_table}
                GROUP BY optimization_run_id
                ORDER BY MAX(optimization_run_date) DESC
                LIMIT {limit}
            '''
            df = query_df(query)
            if not df.empty:
                runs = df.to_dict("records")
                logger.info(f"Found {len(runs)} optimization runs from results")
                return {"runs": runs, "count": len(runs)}
        
        # Fallback to submissions table
        submissions_table = db_config.optimization_runs_table
        if check_table_exists(submissions_table):
            query = f'''
                SELECT DISTINCT "RUN_ID" as run_id,
                       MAX("SUBMISSION_TIMESTAMP") as timestamp,
                       COUNT(*) as sku_count
                FROM {submissions_table}
                GROUP BY "RUN_ID"
                ORDER BY MAX("SUBMISSION_TIMESTAMP") DESC
                LIMIT {limit}
            '''
            df = query_df(query)
            if not df.empty:
                runs = df.to_dict("records")
                logger.info(f"Found {len(runs)} runs from submissions")
                return {"runs": runs, "count": len(runs)}
        
        return {"runs": [], "count": 0}
        
    except Exception as e:
        logger.error(f"Error fetching optimization runs: {e}")
        return {"runs": [], "count": 0, "error": str(e)}


@app.get("/api/optimization-runs/{run_id}")
async def get_optimization_results(run_id: str):
    """
    Get optimization results for a specific run.
    Used by ui_app results page grid.
    """
    from .database import query_df, check_table_exists
    from .config import db_config
    
    logger.info(f"GET /api/optimization-runs/{run_id}")
    
    try:
        table = db_config.opt_planogram_table
        
        if not check_table_exists(table):
            raise HTTPException(status_code=404, detail="No optimization results table found")
        
        query = f"SELECT * FROM {table} WHERE optimization_run_id = %s"
        df = query_df(query, (run_id,))
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
        
        # Uppercase column names for UI consistency
        df.columns = [col.upper() for col in df.columns]
        
        # Convert to records
        records = df.to_dict("records")
        
        # Generate summary (using uppercase column names)
        numeric_cols = ["RECOMMENDED_FACINGS", "FACINGS_CHANGE", "EXPECTED_MARGIN_WEEKLY"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        ranged_df = df[df['IS_RANGED_RECOMMENDED'] == True] if 'IS_RANGED_RECOMMENDED' in df.columns else df
        
        change_col = 'CHANGE_FROM_CURRENT' if 'CHANGE_FROM_CURRENT' in df.columns else None
        summary = {
            "run_id": run_id,
            "total_skus": len(df),
            "skus_in_range": len(ranged_df),
            "skus_added": len(df[df[change_col] == 'new']) if change_col else 0,
            "skus_removed": len(df[df[change_col] == 'removed']) if change_col else 0,
            "skus_increased": len(df[df[change_col] == 'increased']) if change_col else 0,
            "skus_decreased": len(df[df[change_col] == 'decreased']) if change_col else 0,
            "total_facings": int(ranged_df["RECOMMENDED_FACINGS"].sum()) if "RECOMMENDED_FACINGS" in ranged_df.columns else 0,
            "total_weekly_profit": float(ranged_df["EXPECTED_MARGIN_WEEKLY"].sum()) if "EXPECTED_MARGIN_WEEKLY" in ranged_df.columns else 0,
        }
        
        # Replace NaN/NA values to keep JSON serialization happy
        df = df.replace({pd.NA: None, np.nan: None})
        summary = {k: (None if pd.isna(v) else v) for k, v in summary.items()}
        
        logger.info(f"Returning {len(records)} results for run {run_id}")
        return {"results": df.to_dict("records"), "summary": summary, "count": len(df)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching optimization results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimization-runs")
async def submit_optimization_run(request: OptimizationRunRequest):
    """
    Submit a new optimization run.
    Saves data to optimization_runs table and triggers optimization.
    """
    from .database import bulk_insert
    from .config import db_config
    from .mcp.tools import run_range_optimization_logic
    import datetime
    import uuid
    
    logger.info(f"POST /api/optimization-runs - {len(request.records)} SKUs")
    
    try:
        # Generate run ID
        run_id = f"OPT-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        timestamp = datetime.datetime.now().isoformat()
        
        # Prepare data
        records = [r.model_dump(exclude_none=True) for r in request.records]
        df = pd.DataFrame(records)
        df["RUN_ID"] = run_id
        df["SUBMISSION_TIMESTAMP"] = timestamp
        df["ROW_ID"] = [f"{run_id}-{i+1:04d}" for i in range(len(df))]
        
        # Save to database
        table = db_config.optimization_runs_table
        rows = bulk_insert(table, df, overwrite=False)
        logger.info(f"Saved {rows} records for run {run_id}")
        
        # Trigger optimization
        result = run_range_optimization_logic(run_id, "stock-optimization-model")
        
        return {
            "run_id": run_id,
            "timestamp": timestamp,
            "sku_count": rows,
            "optimization_status": result.get("status", "unknown"),
            "optimization_result": result
        }
        
    except Exception as e:
        logger.error(f"Error submitting optimization run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Optimization Trigger Endpoint (existing, kept for compatibility)
# =============================================================================

@app.post("/api/run_optimization")
async def run_optimization(request: OptimizationRequest):
    """Trigger range optimization manually"""
    from .mcp.tools import run_range_optimization_logic
    return run_range_optimization_logic(request.forecast_id, request.model_endpoint)


@app.post("/api/insights")
@mlflow.trace(name="generate_insights")
async def generate_insights(request: InsightsRequest):
    """Generate AI insights for an optimization run's planogram recommendations."""
    # Add context to trace
    mlflow.update_current_trace(tags={"context": "range optimizer", "run_id": request.forecast_id})
    from .database import query_df, get_workspace_client, check_table_exists
    from .config import db_config
    
    run_id = request.forecast_id  # Keep param name for API compatibility
    logger.info(f"Generating insights for optimization run: {run_id}")
    
    try:
        # 1. Fetch optimization results from opt_recommended_planogram
        table = db_config.opt_planogram_table
        
        # Check if table exists first
        if not check_table_exists(table):
            return {
                "forecast_id": run_id,
                "insights": "No optimization results yet. Submit an optimization run to generate recommendations.",
                "source": "info",
                "tools_used": []
            }
        
        query = f"SELECT * FROM {table} WHERE optimization_run_id = %s"
        df = query_df(query, (run_id,))
        
        if df.empty:
            return {
                "forecast_id": run_id,
                "insights": "No optimization results found for this run. Try selecting a different run.",
                "source": "info",
                "tools_used": []
            }
        
        # 2. Convert numeric columns (new schema columns)
        import pandas as pd
        numeric_cols = ["recommended_facings", "facings_change", "expected_units_weekly", 
                       "expected_sales_value_weekly", "expected_margin_weekly"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # 3. Calculate summary statistics (new schema)
        total_skus = len(df)
        ranged_df = df[df['is_ranged_recommended'] == True] if 'is_ranged_recommended' in df.columns else df
        skus_ranged = len(ranged_df)
        total_facings = ranged_df["recommended_facings"].sum() if "recommended_facings" in ranged_df.columns else 0
        total_weekly_profit = ranged_df["expected_margin_weekly"].sum() if "expected_margin_weekly" in ranged_df.columns else 0
        total_weekly_revenue = ranged_df["expected_sales_value_weekly"].sum() if "expected_sales_value_weekly" in ranged_df.columns else 0
        
        # Count changes
        skus_added = len(df[df['change_from_current'] == 'new']) if 'change_from_current' in df.columns else 0
        skus_removed = len(df[df['change_from_current'] == 'removed']) if 'change_from_current' in df.columns else 0
        skus_increased = len(df[df['change_from_current'] == 'increased']) if 'change_from_current' in df.columns else 0
        skus_decreased = len(df[df['change_from_current'] == 'decreased']) if 'change_from_current' in df.columns else 0
        
        # Get top performers by weekly profit
        if "expected_margin_weekly" in ranged_df.columns and len(ranged_df) > 0:
            top_skus = ranged_df.nlargest(3, "expected_margin_weekly")["sku_id"].tolist()
        else:
            top_skus = []
        
        # 3. Generate insights using LLM
        w = get_workspace_client()
        
        token_headers = w.config.authenticate()
        api_key = token_headers.get("Authorization", "").replace("Bearer ", "")
        host = w.config.host
        
        if not api_key:
             logger.warning("No Databricks token could be retrieved from WorkspaceClient")
        
        client = OpenAI(
            api_key=api_key,
            base_url=f"{host.rstrip('/')}/serving-endpoints"
        )
        
        prompt = f"""Analyze this range optimization summary and provide 3-4 key business insights:

Run ID: {run_id}
Total SKUs Evaluated: {total_skus}
SKUs in Range: {skus_ranged}
Total Facings Allocated: {total_facings:.0f}
Expected Weekly Profit: ${total_weekly_profit:,.2f}
Expected Weekly Revenue: ${total_weekly_revenue:,.2f}

Changes:
- SKUs Added to Range: {skus_added}
- SKUs Removed from Range: {skus_removed}  
- SKUs with Increased Facings: {skus_increased}
- SKUs with Decreased Facings: {skus_decreased}

Top Performing SKUs: {', '.join(str(s) for s in top_skus[:3])}

Provide concise, actionable insights focusing on range efficiency, space optimization, and recommendations.
Format as bullet points. Keep each insight to 1-2 sentences."""

        try:
            response = client.chat.completions.create(
                model="databricks-meta-llama-3-3-70b-instruct",
                messages=[
                    {"role": "system", "content": "You are a retail range optimization assistant. Provide clear, actionable business insights about planogram and assortment optimization."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            
            insights = response.choices[0].message.content
            logger.info(f"Generated insights: {len(insights)} chars")
            
            return {
                "forecast_id": run_id,
                "insights": insights,
                "source": "mcp-server",
                "tools_used": ["get_optimization_results", "llm_analysis"]
            }
            
        except Exception as llm_err:
            logger.warning(f"LLM call failed, using fallback: {llm_err}")
            
            # Fallback to statistical insights
            insights = f"""• **Range Efficiency**: {skus_ranged} of {total_skus} SKUs recommended for range with {total_facings:.0f} total facings.
• **Profit Potential**: Expected weekly profit of ${total_weekly_profit:,.2f} (${total_weekly_profit * 52:,.2f} annually).
• **Assortment Changes**: {skus_added} SKUs added, {skus_removed} removed, {skus_increased + skus_decreased} facings adjusted.
• **Top Performers**: Focus on {', '.join(str(s) for s in top_skus[:2])} for highest margin contribution."""
            
            return {
                "forecast_id": run_id,
                "insights": insights,
                "source": "fallback",
                "tools_used": ["get_optimization_results"]
            }
            
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return {
            "forecast_id": run_id,
            "insights": f"Error generating insights: {str(e)}",
            "source": "error",
            "error": str(e),
            "tools_used": []
        }


@app.post("/api/chat")
@mlflow.trace(name="chat_assistant")
async def chat(request: ChatRequest):
    """Handle chat messages with AI responses using planogram optimization data."""
    # Add context to trace
    mlflow.update_current_trace(tags={"context": "range optimizer", "run_id": request.forecast_id})
    from .database import query_df, get_workspace_client, check_table_exists
    from .config import db_config
    
    run_id = request.forecast_id  # Keep param name for API compatibility
    logger.info(f"Chat request for optimization run: {run_id}")
    logger.info(f"Question: {request.question[:100]}...")
    
    try:
        # 1. Fetch relevant optimization data from opt_recommended_planogram
        table = db_config.opt_planogram_table
        
        if not check_table_exists(table):
            return {
                "forecast_id": run_id,
                "question": request.question,
                "answer": "No optimization data available yet. Submit an optimization run to generate planogram recommendations.",
                "source": "info",
                "tools_used": []
            }
        
        query = f"SELECT * FROM {table} WHERE optimization_run_id = %s"
        df = query_df(query, (run_id,))
        
        if df.empty:
            return {
                "forecast_id": run_id,
                "question": request.question,
                "answer": "No optimization data found for this run. Please select a different run or submit a new optimization.",
                "source": "info",
                "tools_used": []
            }
        
        # 2. Convert numeric columns (new schema columns)
        import pandas as pd
        numeric_cols = ["recommended_facings", "facings_change", "expected_units_weekly", 
                       "expected_sales_value_weekly", "expected_margin_weekly"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # 3. Build context from new schema data
        ranged_df = df[df['is_ranged_recommended'] == True] if 'is_ranged_recommended' in df.columns else df
        
        summary = {
            "total_skus": len(df),
            "skus_ranged": len(ranged_df),
            "total_facings": ranged_df["recommended_facings"].sum() if "recommended_facings" in ranged_df.columns else 0,
            "weekly_profit": ranged_df["expected_margin_weekly"].sum() if "expected_margin_weekly" in ranged_df.columns else 0,
            "weekly_revenue": ranged_df["expected_sales_value_weekly"].sum() if "expected_sales_value_weekly" in ranged_df.columns else 0,
        }
        
        # Get category breakdown
        if "category" in df.columns:
            cat_summary = ranged_df.groupby("category").agg({
                "expected_margin_weekly": "sum",
                "recommended_facings": "sum",
                "sku_id": "count"
            }).rename(columns={"sku_id": "sku_count"}).head(5).to_string()
        else:
            cat_summary = "Category data not available"
        
        # 3. Call LLM with context
        w = get_workspace_client()
        
        token_headers = w.config.authenticate()
        api_key = token_headers.get("Authorization", "").replace("Bearer ", "")
        host = w.config.host
        
        if not api_key:
             logger.warning("No Databricks token could be retrieved from WorkspaceClient")
        
        client = OpenAI(
            api_key=api_key,
            base_url=f"{host.rstrip('/')}/serving-endpoints"
        )
        
        data_context = f"""You have access to range optimization results for run {run_id}:

Summary:
- Total SKUs Evaluated: {summary['total_skus']}
- SKUs in Recommended Range: {summary['skus_ranged']}
- Total Facings Allocated: {summary['total_facings']:.0f}
- Expected Weekly Revenue: ${summary['weekly_revenue']:,.2f}
- Expected Weekly Profit: ${summary['weekly_profit']:,.2f}
- Estimated Annual Profit: ${summary['weekly_profit'] * 52:,.2f}

Category Breakdown:
{cat_summary}

{f"Previous context: {request.context}" if request.context else ""}

SKU-level planogram recommendations are available for detailed queries."""

        try:
            response = client.chat.completions.create(
                model="databricks-meta-llama-3-3-70b-instruct",
                messages=[
                    {"role": "system", "content": f"You are a retail range optimization assistant helping with planogram and assortment decisions. Answer questions based on this data:\n{data_context}"},
                    {"role": "user", "content": request.question}
                ],
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            logger.info(f"Generated answer: {len(answer)} chars")
            
            return {
                "forecast_id": run_id,
                "question": request.question,
                "answer": answer,
                "source": "mcp-server",
                "tools_used": ["get_optimization_results", "llm_chat"]
            }
            
        except Exception as llm_err:
            logger.warning(f"LLM call failed: {llm_err}")
            
            # Fallback response
            return {
                "forecast_id": run_id,
                "question": request.question,
                "answer": f"I'm having trouble connecting to the AI service. Here's what I know about this optimization run:\n\n• {summary['skus_ranged']} SKUs in recommended range (of {summary['total_skus']} evaluated)\n• {summary['total_facings']:.0f} total facings allocated\n• ${summary['weekly_profit']:,.2f} expected weekly profit\n\nPlease try again or ask a more specific question.",
                "source": "fallback",
                "tools_used": ["get_optimization_results"]
            }
            
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return {
            "forecast_id": run_id,
            "question": request.question,
            "answer": f"Error processing your question: {str(e)}",
            "source": "error",
            "error": str(e),
            "tools_used": []
        }
