"""
MCP Tools for Inventory Intelligence.

This module defines all the tools that the MCP server exposes to AI clients.
Tools provide access to inventory forecasts, stock optimization results,
and product insights from the Databricks Lakebase PostgreSQL database.
"""

import datetime
from typing import Optional
from ..database import query_df, bulk_insert, get_workspace_client
from ..config import db_config
from ..logger import logger


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    logger.info(f"[MCP] {message}")


def register_tools(mcp_server):
    """Register all MCP tools with the server."""

    @mcp_server.tool
    def health() -> dict:
        """Check the health of the MCP server and database connection."""
        try:
            from ..database import get_connection_pool
            pool = get_connection_pool()
            if pool:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1 as test")
                        cur.fetchone()
                db_status = "connected"
            else:
                db_status = "no pool"
        except Exception as e:
            db_status = f"error: {str(e)}"
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "database": db_status
        }

    @mcp_server.tool
    def get_current_user() -> dict:
        """Get information about the current authenticated user."""
        try:
            w = get_workspace_client()
            user = w.current_user.me()
            return {
                "display_name": user.display_name,
                "user_name": user.user_name,
                "active": user.active
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def get_forecast_runs() -> dict:
        """
        Get all available forecast runs that have optimization results.
        
        Returns a list of forecast runs with their submission timestamps
        and the number of products optimized.
        """
        try:
            table = db_config.get_full_table_name("stock_optimization_results")
            query = f"""
                SELECT DISTINCT forecast_id, 
                       MAX(optimization_timestamp) as ts, 
                       COUNT(*) as cnt
                FROM {table} 
                GROUP BY forecast_id 
                ORDER BY MAX(optimization_timestamp) DESC
            """
            df = query_df(query)
            forecasts = [
                {
                    "forecast_id": row["forecast_id"],
                    "submission_timestamp": str(row["ts"]),
                    "product_count": row["cnt"]
                }
                for _, row in df.iterrows()
            ]
            return {"forecasts": forecasts, "total_count": len(forecasts)}
        except Exception as e:
            return {"error": str(e), "forecasts": [], "total_count": 0}

    @mcp_server.tool
    def get_optimization_results(forecast_id: str) -> dict:
        """
        Get stock optimization results for a specific forecast run.
        
        Args:
            forecast_id: The unique identifier of the forecast run
            
        Returns:
            Optimization results including optimal stock levels, reorder points,
            and financial metrics for each product.
        """
        try:
            table = db_config.get_full_table_name("stock_optimization_results")
            query = f"SELECT * FROM {table} WHERE forecast_id = %s"
            df = query_df(query, (forecast_id,))
            products = df.to_dict(orient="records")
            
            # Calculate summary statistics
            summary = {}
            if not df.empty:
                summary = {
                    "product_count": len(df),
                    "total_annual_cost": df["total_annual_cost"].sum() if "total_annual_cost" in df else 0,
                    "total_annual_profit": df["expected_annual_profit"].sum() if "expected_annual_profit" in df else 0,
                    "avg_service_level": df["service_level"].mean() if "service_level" in df else 0,
                }
            
            return {
                "forecast_id": forecast_id,
                "products": products,
                "summary": summary
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def recommend_restocking(
        forecast_id: Optional[str] = None,
        min_urgency: float = 0.5,
        limit: int = 20
    ) -> dict:
        """
        Get prioritized restocking recommendations based on optimization results.
        
        Args:
            forecast_id: Optional - use latest forecast if not specified
            min_urgency: Minimum urgency score (0-1) to include
            limit: Maximum number of recommendations to return
            
        Returns:
            Prioritized list of products that need restocking, sorted by urgency.
        """
        try:
            table = db_config.get_full_table_name("stock_optimization_results")
            
            # Get latest forecast if not specified
            if not forecast_id:
                latest_query = f"""
                    SELECT forecast_id FROM {table} 
                    ORDER BY optimization_timestamp DESC LIMIT 1
                """
                df = query_df(latest_query)
                if df.empty:
                    return {"error": "No forecast results found"}
                forecast_id = df.iloc[0]["forecast_id"]
            
            query = f"""
                SELECT product_name, category_name, subcategory_name,
                       optimal_order_qty, safety_stock, reorder_point,
                       avg_daily_demand, service_level
                FROM {table}
                WHERE forecast_id = %s
                ORDER BY optimal_order_qty DESC
                LIMIT %s
            """
            df = query_df(query, (forecast_id, limit))
            
            recommendations = []
            for _, row in df.iterrows():
                # Calculate urgency based on demand vs safety stock ratio
                demand = row.get("avg_daily_demand", 1)
                safety = row.get("safety_stock", 0)
                urgency = min(1.0, demand / max(safety, 1) * 0.5)
                
                if urgency >= min_urgency:
                    recommendations.append({
                        "product_name": row["product_name"],
                        "category": row["category_name"],
                        "subcategory": row["subcategory_name"],
                        "recommended_order_qty": row["optimal_order_qty"],
                        "reorder_point": row["reorder_point"],
                        "urgency_score": round(urgency, 2)
                    })
            
            return {
                "forecast_id": forecast_id,
                "recommendations": sorted(recommendations, key=lambda x: -x["urgency_score"]),
                "count": len(recommendations)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def get_category_insights(category_name: str) -> dict:
        """
        Analyze a product category across all forecasts.
        
        Args:
            category_name: The category to analyze (e.g., "Dairy", "Frozen")
            
        Returns:
            Category-level insights including product count, average metrics,
            and trends across forecast runs.
        """
        try:
            table = db_config.get_full_table_name("stock_optimization_results")
            query = f"""
                SELECT forecast_id, 
                       COUNT(*) as product_count,
                       AVG(optimal_order_qty) as avg_order_qty,
                       AVG(safety_stock) as avg_safety_stock,
                       SUM(expected_annual_profit) as total_profit,
                       AVG(service_level) as avg_service_level,
                       MAX(optimization_timestamp) as timestamp
                FROM {table}
                WHERE category_name = %s
                GROUP BY forecast_id
                ORDER BY MAX(optimization_timestamp) DESC
            """
            df = query_df(query, (category_name,))
            
            forecasts = df.to_dict(orient="records")
            
            return {
                "category": category_name,
                "forecast_history": forecasts,
                "total_forecasts": len(forecasts)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool  
    def compare_forecasts(forecast_id_1: str, forecast_id_2: str) -> dict:
        """
        Compare optimization results between two forecast runs.
        
        Args:
            forecast_id_1: First forecast to compare
            forecast_id_2: Second forecast to compare
            
        Returns:
            Comparison showing changes in key metrics between forecasts.
        """
        try:
            table = db_config.get_full_table_name("stock_optimization_results")
            
            def get_summary(fid):
                query = f"""
                    SELECT COUNT(*) as product_count,
                           SUM(optimal_order_qty) as total_order_qty,
                           SUM(expected_annual_profit) as total_profit,
                           AVG(service_level) as avg_service_level
                    FROM {table}
                    WHERE forecast_id = %s
                """
                df = query_df(query, (fid,))
                if df.empty:
                    return None
                return df.iloc[0].to_dict()
            
            summary_1 = get_summary(forecast_id_1)
            summary_2 = get_summary(forecast_id_2)
            
            if not summary_1 or not summary_2:
                return {"error": "One or both forecasts not found"}
            
            # Calculate differences
            changes = {}
            for key in summary_1:
                v1 = float(summary_1[key] or 0)
                v2 = float(summary_2[key] or 0)
                changes[key] = {
                    "forecast_1": v1,
                    "forecast_2": v2,
                    "change": v2 - v1,
                    "change_pct": ((v2 - v1) / v1 * 100) if v1 != 0 else 0
                }
            
            return {
                "forecast_id_1": forecast_id_1,
                "forecast_id_2": forecast_id_2,
                "comparison": changes
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def get_product_details(product_name: str) -> dict:
        """
        Get historical optimization data for a specific product.
        
        Args:
            product_name: The product name to look up
            
        Returns:
            All optimization results for this product across forecast runs.
        """
        try:
            table = db_config.get_full_table_name("stock_optimization_results")
            query = f"""
                SELECT * FROM {table}
                WHERE product_name = %s
                ORDER BY optimization_timestamp DESC
            """
            df = query_df(query, (product_name,))
            
            return {
                "product_name": product_name,
                "history": df.to_dict(orient="records"),
                "total_entries": len(df)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def run_forecast_optimization(
        forecast_id: str,
        model_endpoint: str = "stock-optimization-model"
    ) -> dict:
        """
        Run the full stock optimization process for a forecast.
        
        Args:
            forecast_id: The forecast ID to optimize
            model_endpoint: Model Serving endpoint name
            
        Returns:
            Status of the optimization run including product count.
        """
        return run_forecast_optimization_logic(forecast_id, model_endpoint)

    log("✓ Registered 9 MCP tools")


def run_forecast_optimization_logic(
    forecast_id: str,
    model_endpoint: str = "stock-optimization-model"
) -> dict:
    """
    Core logic for running stock optimization.
    Extracted from tool to allow direct API access.
    """
    try:
        from databricks.sdk import WorkspaceClient
        
        submissions_table = db_config.get_full_table_name("forecast_submissions")
        results_table = db_config.get_full_table_name("stock_optimization_results")
        
        # 1. Fetch forecast submission data
        query = f'SELECT * FROM {submissions_table} WHERE "FORECAST_ID" = %s'
        df = query_df(query, (forecast_id,))
        
        if df.empty:
            return {
                "forecast_id": forecast_id,
                "model_endpoint": model_endpoint,
                "status": "error",
                "error": f"No forecast data found for ID: {forecast_id}",
                "product_count": 0
            }
        
        forecast_data = df.to_dict(orient="records")
        
        # 2. Transform forecast data (Feature Engineering)
        input_records = []
        category_map = {}
        
        for row in forecast_data:
            base_demand = float(row.get('SHELF_SPACE_CM', 10) or 10) * 10
            sell_id = row['SELL_ID']
            
            record = {
                'sell_id': sell_id,
                'avg_daily_demand': base_demand,
                'demand_std': base_demand * 0.2,
                'total_forecast_30d': base_demand * 30,
                'unit_cost': 10.0,
                'selling_price': 20.0,
                'current_stock': 0,
                'safety_stock': 0
            }
            input_records.append(record)
            
            category_map[sell_id] = {
                'category': row.get('CATEGORY_NAME', 'Unknown'),
                'subcategory': row.get('SUBCATEGORY_NAME', 'Unknown'),
                'product_name': row.get('PRODUCT_NAME', 'Unknown')
            }
        
        # 3. Invoke Model Serving
        w = get_workspace_client()
        
        serving_input = {
            "sell_id": [r["sell_id"] for r in input_records],
            "avg_daily_demand": [r["avg_daily_demand"] for r in input_records],
            "current_stock": [r["current_stock"] for r in input_records],
            "safety_stock": [r["safety_stock"] for r in input_records],
        }
        
        try:
            response = w.serving_endpoints.query(
                name=model_endpoint,
                dataframe_records=serving_input
            )
            predictions = response.predictions if hasattr(response, 'predictions') else []
            method_used = "model_serving"
        except Exception as model_err:
            log(f"Model serving failed, using fallback: {model_err}")
            # Fallback heuristic optimization
            predictions = []
            for rec in input_records:
                demand = rec['avg_daily_demand']
                qty = (2 * demand * 50 / 0.2) ** 0.5
                predictions.append({
                    "optimal_order_qty": qty,
                    "safety_stock": demand * 2,
                    "reorder_point": demand * 5,
                    "max_stock_level": qty + (demand * 2),
                    "total_annual_cost": qty * 10,
                    "expected_annual_revenue": qty * 20,
                    "expected_annual_profit": qty * 10,
                    "turnover_rate": 10.0,
                    "service_level": 0.95
                })
            method_used = "fallback_heuristic"
        
        # 4. Save results
        import pandas as pd
        timestamp = datetime.datetime.now().isoformat()
        
        results_to_save = []
        for i, pred in enumerate(predictions):
            if not isinstance(pred, dict):
                pred = {}
            
            sell_id = input_records[i]['sell_id']
            cat_info = category_map.get(sell_id, {})
            
            results_to_save.append({
                "forecast_id": forecast_id,
                "sell_id": sell_id,
                "product_name": cat_info.get('product_name'),
                "category_name": cat_info.get('category'),
                "subcategory_name": cat_info.get('subcategory'),
                "avg_daily_demand": input_records[i]['avg_daily_demand'],
                "optimal_order_qty": pred.get("optimal_order_qty", input_records[i]['avg_daily_demand'] * 7),
                "safety_stock": pred.get("safety_stock", input_records[i]['avg_daily_demand'] * 2),
                "reorder_point": pred.get("reorder_point", input_records[i]['avg_daily_demand'] * 4),
                "max_stock_level": pred.get("max_stock_level", input_records[i]['avg_daily_demand'] * 10),
                "total_annual_cost": pred.get("total_annual_cost", 0),
                "expected_annual_revenue": pred.get("expected_annual_revenue", 0),
                "expected_annual_profit": pred.get("expected_annual_profit", 0),
                "turnover_rate": pred.get("turnover_rate", 0),
                "service_level": pred.get("service_level", 0.95),
                "optimization_method": method_used,
                "optimization_timestamp": timestamp
            })
        
        results_df = pd.DataFrame(results_to_save)
        bulk_insert(results_table, results_df, overwrite=False)
        
        return {
            "forecast_id": forecast_id,
            "model_endpoint": model_endpoint,
            "status": "success",
            "product_count": len(results_to_save),
            "method": method_used
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "forecast_id": forecast_id,
            "model_endpoint": model_endpoint,
            "status": "error",
            "error": str(e),
            "product_count": 0
        }


