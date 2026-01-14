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
    # ValidationRequest, ValidationResult, ValidationIssue - defined in mcp_standalone.py
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
# Validation Endpoint
# ============================================================
# NOTE: The /api/validate endpoint is defined in mcp_standalone.py
# which is the actual app entry point. This router is NOT loaded.
# Keeping this commented out to avoid confusion about duplicates.
#
# The validation logic lives in mcp_standalone.py:validate_data()


# ============================================================
# Categories Endpoints
# ============================================================

@api.get("/categories", response_model=CategoriesListOut, operation_id="listCategories")
async def list_categories():
    """Get list of available categories with product counts"""
    table_name = db_config.get_full_table_name(db_config.TABLE_DIM_SKU)
    
    if not check_table_exists(table_name):
        return CategoriesListOut(categories=[])
    
    query = f'''
        SELECT "CATEGORY" as name, COUNT(*) as product_count
        FROM {table_name}
        GROUP BY "CATEGORY"
        ORDER BY "CATEGORY"
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
    """Get SKU data for layout, optionally filtered by category"""
    table_name = db_config.get_full_table_name(db_config.TABLE_DIM_SKU)
    
    if not check_table_exists(table_name):
        return []
    
    if category and category != "All":
        query = f'SELECT * FROM {table_name} WHERE "CATEGORY" = %s'
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
    """Save SKU data (batch insert)"""
    table_name = db_config.get_full_table_name(db_config.TABLE_DIM_SKU)
    
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
        logger.error(f"Failed to save SKU data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Forecast Endpoints
# ============================================================

@api.post("/forecasts", response_model=ForecastSubmissionOut, operation_id="submitForecast")
async def submit_forecast(data: ForecastSubmissionIn):
    """Submit a new optimization run"""
    table_name = db_config.get_full_table_name(db_config.TABLE_OPTIMIZATION_RUNS)
    
    # Generate run ID
    run_id = f"RUN-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
    timestamp = datetime.datetime.now()
    
    # Convert to DataFrame and add metadata
    records = [r.model_dump(by_alias=True) for r in data.records]
    df = pd.DataFrame(records)
    df["RUN_ID"] = run_id
    df["SUBMISSION_TIMESTAMP"] = timestamp.isoformat()
    df["ROW_ID"] = [f"{run_id}-{i+1:04d}" for i in range(len(df))]
    
    try:
        rows = bulk_insert(table_name, df, overwrite=False)
        
        # Optionally trigger optimization via MCP
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{conf.mcp_server_url}/api/run_optimization",
                    json={"forecast_id": run_id},
                    timeout=30.0
                )
                if response.status_code == 200:
                    logger.info(f"Optimization triggered for {run_id}")
        except Exception as e:
            logger.warning(f"Failed to trigger optimization: {e}")
        
        return ForecastSubmissionOut(
            forecast_id=run_id,
            submission_timestamp=timestamp,
            row_count=rows,
            message=f"Optimization run submitted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to submit optimization run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/forecasts", response_model=ForecastListOut, operation_id="listForecasts")
async def list_forecasts(
    limit: Optional[int] = Query(20, description="Limit number of results"),
):
    """Get list of submitted optimization runs"""
    table_name = db_config.get_full_table_name(db_config.TABLE_OPTIMIZATION_RUNS)
    
    if not check_table_exists(table_name):
        return ForecastListOut(forecasts=[], total=0)
    
    query = f'''
        SELECT 
            "RUN_ID" as forecast_id,
            MIN("SUBMISSION_TIMESTAMP") as submission_timestamp,
            COUNT(*) as row_count,
            COUNT(DISTINCT "CATEGORY") as category_count
        FROM {table_name}
        GROUP BY "RUN_ID"
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
    """Get planogram optimization results for a run"""
    table_name = db_config.opt_planogram_table
    
    if not check_table_exists(table_name):
        raise HTTPException(status_code=404, detail="No optimization results found")
    
    query = f'''
        SELECT * FROM {table_name}
        WHERE optimization_run_id = %s
        ORDER BY expected_margin_weekly DESC
    '''
    
    df = query_df(query, (forecast_id,))
    
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No optimization results for run {forecast_id}")
    
    # Build results (map new schema to existing API model for compatibility)
    results = []
    for _, row in df.iterrows():
        results.append(StockOptimizationOut(
            forecast_id=row.get('optimization_run_id', forecast_id),
            sell_id=row.get('sku_id', ''),
            product_name=row.get('sku_name', row.get('sku_id', '')),
            category_name=row.get('category', ''),
            current_stock=int(row.get('current_facings', 0)),  # Map facings to stock for API compat
            predicted_demand=float(row.get('expected_units_weekly', 0)),
            optimal_stock=int(row.get('recommended_facings', 0)),
            reorder_quantity=int(row.get('facings_change', 0)),
            confidence_score=float(row.get('score', 0)),
            recommendation=row.get('change_from_current', 'No change'),
        ))
    
    # Build summary
    products_needing_change = sum(1 for r in results if r.reorder_quantity != 0)
    total_facings_change = sum(r.reorder_quantity for r in results)
    avg_score = sum(r.confidence_score for r in results) / len(results) if results else 0
    
    summary = OptimizationSummaryOut(
        forecast_id=forecast_id,
        total_products=len(results),
        products_needing_reorder=products_needing_change,
        total_reorder_quantity=total_facings_change,
        avg_confidence_score=avg_score
    )
    
    return OptimizationResultsOut(summary=summary, results=results)


@api.get("/forecasts-with-optimization", response_model=List[str], operation_id="listForecastsWithOptimization")
async def list_forecasts_with_optimization():
    """Get list of run IDs that have optimization results"""
    table_name = db_config.opt_planogram_table
    
    if not check_table_exists(table_name):
        return []
    
    query = f'''
        SELECT DISTINCT optimization_run_id as forecast_id
        FROM {table_name}
        ORDER BY optimization_run_id DESC
    '''
    
    df = query_df(query)
    return df['forecast_id'].tolist() if not df.empty else []


@api.post("/run_optimization", operation_id="runOptimization")
async def run_optimization(payload: dict):
    """
    Trigger range optimization using ML serving endpoint with Feature Store.

    This endpoint:
    1. Reads the submitted forecast data (SKU_IDs)
    2. Fetches features from Feature Store (Unity Catalog)
    3. Calls ML serving endpoint for predictions
    4. Writes optimized results to opt_planogram table

    Args:
        payload: Dict with 'forecast_id' or 'run_id'

    Returns:
        Status and SKU count
    """
    forecast_id = payload.get("forecast_id") or payload.get("run_id")

    if not forecast_id:
        raise HTTPException(status_code=400, detail="Missing forecast_id or run_id")

    logger.info(f"Running ML optimization for forecast: {forecast_id}")

    # Read submitted forecast data
    runs_table = db_config.get_full_table_name(db_config.TABLE_OPTIMIZATION_RUNS)
    query = f'SELECT * FROM {runs_table} WHERE "RUN_ID" = %s'

    try:
        forecast_df = query_df(query, (forecast_id,))

        if forecast_df.empty:
            raise HTTPException(status_code=404, detail=f"Forecast {forecast_id} not found")

        logger.info(f"Found {len(forecast_df)} SKUs to optimize")

        # Get SKU_IDs from forecast
        sku_ids = forecast_df['SKU_ID'].tolist()
        sku_ids_str = "','".join(sku_ids)

        # Fetch features from Feature Store (Unity Catalog)
        logger.info("Fetching features from Feature Store...")
        try:
            from databricks.sdk.runtime import spark

            features_query = f"""
                SELECT
                    p.SKU_ID,
                    p.SKU_NAME,
                    p.UNIT_COST,
                    p.UNIT_PRICE,
                    p.CATEGORY,
                    p.SEGMENT,
                    p.BRAND,
                    p.PACK_WIDTH_MM,
                    p.IS_MUST_STOCK,
                    p.IS_PRIVATE_LABEL,
                    p.CURRENT_FACINGS,
                    d.WEEKLY_UNITS,
                    d.DEMAND_STD,
                    d.FORECAST_4W
                FROM smarter_forecasting.stock_optimization.sku_features p
                JOIN smarter_forecasting.stock_optimization.demand_features d
                    ON p.SKU_ID = d.SKU_ID
                WHERE p.SKU_ID IN ('{sku_ids_str}')
            """

            features_df = spark.sql(features_query).toPandas()
            logger.info(f"Fetched features for {len(features_df)} SKUs from Feature Store")

        except Exception as e:
            logger.error(f"Failed to fetch features from Feature Store: {e}")
            raise HTTPException(status_code=500, detail=f"Feature Store error: {str(e)}")

        # Call ML serving endpoint
        logger.info("Calling ML serving endpoint...")
        try:
            from databricks.sdk import WorkspaceClient
            import requests

            w = WorkspaceClient()
            endpoint_name = "range-optimizer-model"
            endpoint_url = f"{w.config.host}/serving-endpoints/{endpoint_name}/invocations"

            payload_data = {
                "dataframe_records": features_df.to_dict(orient='records')
            }

            headers = {
                "Authorization": f"Bearer {w.config.token}",
                "Content-Type": "application/json"
            }

            response = requests.post(endpoint_url, json=payload_data, headers=headers, timeout=120)

            if response.status_code != 200:
                logger.error(f"Endpoint returned error {response.status_code}: {response.text}")
                raise HTTPException(status_code=500, detail=f"Endpoint error: {response.text}")

            results_data = response.json()
            logger.info(f"Received predictions from ML endpoint")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to call ML endpoint: {e}")
            raise HTTPException(status_code=500, detail=f"ML endpoint error: {str(e)}")

        # Parse results and prepare for database
        predictions = results_data.get('predictions', [])

        if not predictions:
            raise HTTPException(status_code=500, detail="No predictions returned from ML endpoint")

        # Map predictions to opt_planogram schema
        results = []
        for pred in predictions:
            results.append({
                "optimization_run_id": forecast_id,
                "sku_id": pred.get("sku_id", pred.get("SKU_ID", "")),
                "sku_name": pred.get("sku_name", pred.get("SKU_NAME", "")),
                "category": pred.get("category", pred.get("CATEGORY", "")),
                "segment": pred.get("segment", ""),
                "brand": pred.get("brand", ""),
                "current_facings": int(pred.get("current_facings", 0)),
                "recommended_facings": int(pred.get("recommended_facings", 0)),
                "facings_change": int(pred.get("facings_change", 0)),
                "change_from_current": pred.get("change_from_current", "maintain"),
                "expected_units_weekly": float(pred.get("expected_units_weekly", 0)),
                "expected_margin_weekly": float(pred.get("expected_margin_weekly", 0)),
                "space_productivity": float(pred.get("space_productivity", 0)),
                "score": float(pred.get("score", 0)),
                "is_must_stock": bool(pred.get("is_must_stock", False)),
                "is_private_label": bool(pred.get("is_private_label", False)),
                "optimization_timestamp": datetime.datetime.now().isoformat(),
            })

        # Write results to opt_planogram table
        results_df = pd.DataFrame(results)
        opt_table = db_config.opt_planogram_table

        rows_inserted = bulk_insert(opt_table, results_df, overwrite=False)
        logger.info(f"Wrote {rows_inserted} ML optimization results to {opt_table}")

        return {
            "status": "success",
            "forecast_id": forecast_id,
            "product_count": len(results),
            "message": f"Optimized {len(results)} SKUs using ML endpoint with Feature Store",
            "method": "ml_serving_endpoint"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
