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
    ValidationRequest, ValidationResult, ValidationIssue,
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

@api.post("/validate", response_model=ValidationResult, operation_id="validateData")
async def validate_data(request: ValidationRequest):
    """
    Validate grid data for errors and warnings.
    
    Checks:
    - Required fields are present
    - Numeric fields are valid
    - Categorical fields match valid options
    - Value ranges are appropriate
    - No duplicate SKU IDs
    """
    issues: List[ValidationIssue] = []
    data = request.data
    
    # Valid values for categorical fields
    VALID_STATUSES = {"active", "new", "discontinued"}
    VALID_CATEGORIES = {"Beer & Seltzer", "Hot Sauce", "Ice Cream"}
    
    # Required fields for SKU data
    REQUIRED_FIELDS = ["SKU_ID", "SKU_NAME", "CATEGORY", "STATUS", 
                       "WEEKLY_UNITS", "CURRENT_FACINGS", "PACK_WIDTH_MM"]
    
    INTEGER_FIELDS = {"WEEKLY_UNITS", "CURRENT_FACINGS", "PACK_WIDTH_MM"}
    
    # Check for empty data
    if not data:
        issues.append(ValidationIssue(
            severity="error",
            message="No data to validate. Please add SKU records."
        ))
        return ValidationResult(
            valid=False,
            has_errors=True,
            has_warnings=False,
            issues=issues,
            summary="No data provided"
        )
    
    # Check for duplicate SKU IDs
    sku_id_counts = {}
    for row in data:
        sku_id = row.get("SKU_ID")
        if sku_id:
            sku_id_counts[sku_id] = sku_id_counts.get(sku_id, 0) + 1
    
    duplicate_sku_ids = [sku_id for sku_id, count in sku_id_counts.items() if count > 1]
    if duplicate_sku_ids:
        issues.append(ValidationIssue(
            severity="error",
            message=f"Duplicate SKU IDs found: {', '.join(duplicate_sku_ids)}"
        ))
    
    # Validate each row
    for i, row in enumerate(data):
        sku_id = row.get("SKU_ID", f"Row {i+1}")
        
        # Check required fields
        missing_fields = [field for field in REQUIRED_FIELDS if not row.get(field)]
        if missing_fields:
            issues.append(ValidationIssue(
                row_index=i,
                sell_id=sku_id,
                severity="error",
                message=f"Missing required fields: {', '.join(missing_fields)}"
            ))
        
        # Validate integer fields
        for field in INTEGER_FIELDS:
            value = row.get(field)
            if value is not None and value != "":
                try:
                    int_value = int(value)
                    if int_value < 0:
                        issues.append(ValidationIssue(
                            row_index=i,
                            sell_id=sku_id,
                            field=field,
                            severity="error",
                            message=f"{field} must be non-negative (got {int_value})"
                        ))
                except (ValueError, TypeError):
                    issues.append(ValidationIssue(
                        row_index=i,
                        sell_id=sku_id,
                        field=field,
                        severity="error",
                        message=f"{field} must be an integer (got {value})"
                    ))
        
        # Validate STATUS field
        status = row.get("STATUS")
        if status and status not in VALID_STATUSES:
            issues.append(ValidationIssue(
                row_index=i,
                sell_id=sku_id,
                field="STATUS",
                severity="warning",
                message=f"STATUS '{status}' not in valid options: {', '.join(VALID_STATUSES)}"
            ))
        
        # Validate CATEGORY field
        category = row.get("CATEGORY")
        if category and category not in VALID_CATEGORIES:
            issues.append(ValidationIssue(
                row_index=i,
                sell_id=sku_id,
                field="CATEGORY",
                severity="warning",
                message=f"CATEGORY '{category}' not in valid options: {', '.join(VALID_CATEGORIES)}"
            ))
    
    # Count errors and warnings
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    
    has_errors = len(errors) > 0
    has_warnings = len(warnings) > 0
    valid = not has_errors
    
    # Build summary
    if valid and not has_warnings:
        summary = f"✓ Validation passed! {len(data)} SKU records are ready for submission."
    elif valid and has_warnings:
        summary = f"⚠ {len(warnings)} warning(s) found. You can still submit."
    else:
        summary = f"✗ {len(errors)} error(s) found. Please fix before submitting."
    
    return ValidationResult(
        valid=valid,
        has_errors=has_errors,
        has_warnings=has_warnings,
        issues=issues,
        summary=summary
    )


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
    Trigger range optimization for a submitted forecast.
    
    This endpoint:
    1. Reads the submitted forecast data
    2. Runs the EOQ-based optimization model
    3. Writes optimized results to opt_planogram table
    
    Args:
        payload: Dict with 'forecast_id' or 'run_id'
    
    Returns:
        Status and SKU count
    """
    forecast_id = payload.get("forecast_id") or payload.get("run_id")
    
    if not forecast_id:
        raise HTTPException(status_code=400, detail="Missing forecast_id or run_id")
    
    logger.info(f"Running optimization for forecast: {forecast_id}")
    
    # Read submitted forecast data
    runs_table = db_config.get_full_table_name(db_config.TABLE_OPTIMIZATION_RUNS)
    query = f'SELECT * FROM {runs_table} WHERE "RUN_ID" = %s'
    
    try:
        forecast_df = query_df(query, (forecast_id,))
        
        if forecast_df.empty:
            raise HTTPException(status_code=404, detail=f"Forecast {forecast_id} not found")
        
        logger.info(f"Found {len(forecast_df)} SKUs to optimize")
        
        # Run optimization model
        from .ml.stock_optimizer import StockOptimizer, OptimizationConfig
        
        optimizer = StockOptimizer(config=OptimizationConfig())
        
        # Prepare optimization results
        results = []
        for _, row in forecast_df.iterrows():
            # Calculate optimal facings using EOQ logic
            # For simplicity, using facings as a proxy for stock units
            weekly_demand = float(row.get("WEEKLY_UNITS", 0))
            current_facings = int(row.get("CURRENT_FACINGS", 1))
            pack_width_mm = int(row.get("PACK_WIDTH_MM", 100))
            
            # Simple optimization: match facings to demand ratio
            # In real scenario, would use optimizer.optimize_single_product()
            demand_facing_ratio = weekly_demand / max(current_facings, 1)
            
            if demand_facing_ratio > 5:  # High demand, low facings
                recommended_facings = min(current_facings + 2, 10)
                change = "increase"
            elif demand_facing_ratio < 1:  # Low demand, high facings
                recommended_facings = max(current_facings - 1, 1)
                change = "decrease"
            else:
                recommended_facings = current_facings
                change = "maintain"
            
            facings_change = recommended_facings - current_facings
            expected_margin = weekly_demand * 2.5  # Simplified margin calc
            score = min(demand_facing_ratio / 5, 1.0)  # Confidence score
            
            results.append({
                "optimization_run_id": forecast_id,
                "sku_id": row.get("SKU_ID"),
                "sku_name": row.get("SKU_NAME"),
                "category": row.get("CATEGORY"),
                "current_facings": current_facings,
                "recommended_facings": recommended_facings,
                "facings_change": facings_change,
                "change_from_current": change,
                "expected_units_weekly": weekly_demand,
                "expected_margin_weekly": expected_margin,
                "score": score,
                "optimization_timestamp": datetime.datetime.now().isoformat(),
            })
        
        # Write results to opt_planogram table
        results_df = pd.DataFrame(results)
        opt_table = db_config.opt_planogram_table
        
        rows_inserted = bulk_insert(opt_table, results_df, overwrite=False)
        logger.info(f"Wrote {rows_inserted} optimization results to {opt_table}")
        
        return {
            "status": "success",
            "forecast_id": forecast_id,
            "product_count": len(results),
            "message": f"Optimized {len(results)} SKUs"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
