"""
API Router for the Excel Writeback application.

Provides endpoints for:
- Layout data CRUD operations
- Forecast submission and listing
- Stock optimization results
- Categories listing
"""

from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import User as UserOut
import pandas as pd
import datetime
import uuid
import httpx

from .models import (
    VersionOut,
    LayoutDataIn, LayoutDataOut, LayoutDataBatchIn, LayoutDataBatchOut,
    ForecastSubmissionIn, ForecastSubmissionOut, ForecastSummaryOut, ForecastListOut,
    OptimizationResultsOut, OptimizationSummaryOut, StockOptimizationOut,
    CategoryOut, CategoriesListOut,
)
from .dependencies import get_obo_ws
from .config import conf, db_config
from .database import query_df, query_dict_list, bulk_insert, check_table_exists
from .logger import logger

api = APIRouter(prefix=conf.api_prefix)


# ============================================================
# Version & User Endpoints
# ============================================================

@api.get("/version", response_model=VersionOut, operation_id="version")
async def version():
    """Get application version"""
    return VersionOut.from_metadata()


@api.get("/current-user", response_model=UserOut, operation_id="currentUser")
def me(obo_ws: Annotated[WorkspaceClient, Depends(get_obo_ws)]):
    """Get current user information"""
    return obo_ws.current_user.me()


# ============================================================
# Categories Endpoints
# ============================================================

@api.get("/categories", response_model=CategoriesListOut, operation_id="listCategories")
async def list_categories():
    """Get list of available categories with product counts"""
    table_name = db_config.get_full_table_name("layout_data")
    
    if not check_table_exists(table_name):
        return CategoriesListOut(categories=[])
    
    query = f'''
        SELECT "CATEGORY_NAME" as name, COUNT(*) as product_count
        FROM {table_name}
        GROUP BY "CATEGORY_NAME"
        ORDER BY "CATEGORY_NAME"
    '''
    
    df = query_df(query)
    categories = [
        CategoryOut(name=row['name'], product_count=int(row['product_count']))
        for _, row in df.iterrows()
    ]
    
    return CategoriesListOut(categories=categories)


# ============================================================
# Layout Data Endpoints
# ============================================================

@api.get("/layout-data", response_model=List[LayoutDataOut], operation_id="listLayoutData")
async def list_layout_data(
    category: Optional[str] = Query(None, description="Filter by category name"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
):
    """Get layout data, optionally filtered by category"""
    table_name = db_config.get_full_table_name("layout_data")
    
    if not check_table_exists(table_name):
        return []
    
    if category and category != "All":
        query = f'SELECT * FROM {table_name} WHERE "CATEGORY_NAME" = %s'
        params = (category,)
    else:
        query = f'SELECT * FROM {table_name}'
        params = None
    
    if limit:
        query += f' LIMIT {limit}'
    
    results = query_dict_list(query, params)
    return [LayoutDataOut(**r) for r in results]


@api.post("/layout-data", response_model=LayoutDataBatchOut, operation_id="saveLayoutData")
async def save_layout_data(data: LayoutDataBatchIn):
    """Save layout data (batch insert)"""
    table_name = db_config.get_full_table_name("layout_data")
    
    # Convert to DataFrame
    records = [r.model_dump(by_alias=True) for r in data.records]
    df = pd.DataFrame(records)
    
    try:
        rows = bulk_insert(table_name, df, overwrite=data.overwrite)
        return LayoutDataBatchOut(
            success=True,
            rows_affected=rows,
            message=f"Successfully saved {rows} records"
        )
    except Exception as e:
        logger.error(f"Failed to save layout data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Forecast Endpoints
# ============================================================

@api.post("/forecasts", response_model=ForecastSubmissionOut, operation_id="submitForecast")
async def submit_forecast(data: ForecastSubmissionIn):
    """Submit a new forecast"""
    table_name = db_config.get_full_table_name("forecast_submissions")
    
    # Generate forecast ID
    forecast_id = f"FCST-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
    timestamp = datetime.datetime.now()
    
    # Convert to DataFrame and add metadata
    records = [r.model_dump(by_alias=True) for r in data.records]
    df = pd.DataFrame(records)
    df["FORECAST_ID"] = forecast_id
    df["SUBMISSION_TIMESTAMP"] = timestamp.isoformat()
    df["ROW_ID"] = [f"{forecast_id}-{i+1:04d}" for i in range(len(df))]
    
    try:
        rows = bulk_insert(table_name, df, overwrite=False)
        
        # Optionally trigger optimization via MCP
        try:
            # Get auth headers for app-to-app communication
            mcp_headers = {}
            mcp_url = conf.mcp_server_url
            if "localhost" not in mcp_url and "127.0.0.1" not in mcp_url:
                try:
                    w = WorkspaceClient()
                    mcp_headers = w.config.authenticate()
                except Exception as auth_err:
                    logger.warning(f"Could not get auth headers: {auth_err}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{mcp_url}/api/run_optimization",
                    json={"forecast_id": forecast_id},
                    headers=mcp_headers,
                    timeout=30.0
                )
                if response.status_code == 200:
                    logger.info(f"Optimization triggered for {forecast_id}")
        except Exception as e:
            logger.warning(f"Failed to trigger optimization: {e}")
        
        return ForecastSubmissionOut(
            forecast_id=forecast_id,
            submission_timestamp=timestamp,
            row_count=rows,
            message=f"Forecast submitted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to submit forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/forecasts", response_model=ForecastListOut, operation_id="listForecasts")
async def list_forecasts(
    limit: Optional[int] = Query(20, description="Limit number of results"),
):
    """Get list of submitted forecasts"""
    table_name = db_config.get_full_table_name("forecast_submissions")
    
    if not check_table_exists(table_name):
        return ForecastListOut(forecasts=[], total=0)
    
    query = f'''
        SELECT 
            "FORECAST_ID" as forecast_id,
            MIN("SUBMISSION_TIMESTAMP") as submission_timestamp,
            COUNT(*) as row_count,
            COUNT(DISTINCT "CATEGORY_NAME") as category_count
        FROM {table_name}
        GROUP BY "FORECAST_ID"
        ORDER BY MIN("SUBMISSION_TIMESTAMP") DESC
        LIMIT {limit}
    '''
    
    df = query_df(query)
    forecasts = [
        ForecastSummaryOut(
            forecast_id=row['forecast_id'],
            submission_timestamp=pd.to_datetime(row['submission_timestamp']),
            row_count=int(row['row_count']),
            category_count=int(row['category_count'])
        )
        for _, row in df.iterrows()
    ]
    
    return ForecastListOut(forecasts=forecasts, total=len(forecasts))


# ============================================================
# Stock Optimization Endpoints
# ============================================================

@api.get("/forecasts/{forecast_id}/optimization", response_model=OptimizationResultsOut, operation_id="getOptimizationResults")
async def get_optimization_results(forecast_id: str):
    """Get stock optimization results for a forecast"""
    table_name = db_config.get_full_table_name("stock_optimization_results")
    
    if not check_table_exists(table_name):
        raise HTTPException(status_code=404, detail="No optimization results found")
    
    query = f'''
        SELECT * FROM {table_name}
        WHERE "FORECAST_ID" = %s
        ORDER BY "REORDER_QUANTITY" DESC
    '''
    
    df = query_df(query, (forecast_id,))
    
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No optimization results for forecast {forecast_id}")
    
    # Build results
    results = []
    for _, row in df.iterrows():
        results.append(StockOptimizationOut(
            forecast_id=row.get('FORECAST_ID', forecast_id),
            sell_id=row.get('SELL_ID', ''),
            product_name=row.get('PRODUCT_NAME', ''),
            category_name=row.get('CATEGORY_NAME', ''),
            current_stock=int(row.get('CURRENT_STOCK', 0)),
            predicted_demand=float(row.get('PREDICTED_DEMAND', 0)),
            optimal_stock=int(row.get('OPTIMAL_STOCK', 0)),
            reorder_quantity=int(row.get('REORDER_QUANTITY', 0)),
            confidence_score=float(row.get('CONFIDENCE_SCORE', 0)),
            recommendation=row.get('RECOMMENDATION', 'No recommendation'),
        ))
    
    # Build summary
    products_needing_reorder = sum(1 for r in results if r.reorder_quantity > 0)
    total_reorder = sum(r.reorder_quantity for r in results)
    avg_confidence = sum(r.confidence_score for r in results) / len(results) if results else 0
    
    summary = OptimizationSummaryOut(
        forecast_id=forecast_id,
        total_products=len(results),
        products_needing_reorder=products_needing_reorder,
        total_reorder_quantity=total_reorder,
        avg_confidence_score=avg_confidence
    )
    
    return OptimizationResultsOut(summary=summary, results=results)


@api.get("/forecasts-with-optimization", response_model=List[str], operation_id="listForecastsWithOptimization")
async def list_forecasts_with_optimization():
    """Get list of forecast IDs that have optimization results"""
    table_name = db_config.get_full_table_name("stock_optimization_results")
    
    if not check_table_exists(table_name):
        return []
    
    query = f'''
        SELECT DISTINCT "FORECAST_ID" as forecast_id
        FROM {table_name}
        ORDER BY "FORECAST_ID" DESC
    '''
    
    df = query_df(query)
    return df['forecast_id'].tolist() if not df.empty else []
