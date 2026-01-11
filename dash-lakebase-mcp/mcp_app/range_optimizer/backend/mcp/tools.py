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
    def get_optimization_runs() -> dict:
        """
        Get all available optimization runs that have planogram recommendations.
        
        Returns a list of optimization runs with their submission timestamps
        and the number of SKUs optimized.
        """
        try:
            # Use opt_recommended_planogram table from new schema
            table = db_config.opt_planogram_table
            query = f"""
                SELECT DISTINCT optimization_run_id, 
                       MAX(optimization_run_date) as run_date, 
                       COUNT(*) as sku_count
                FROM {table} 
                GROUP BY optimization_run_id 
                ORDER BY MAX(optimization_run_date) DESC
            """
            df = query_df(query)
            runs = [
                {
                    "run_id": row["optimization_run_id"],
                    "run_date": str(row["run_date"]),
                    "sku_count": row["sku_count"]
                }
                for _, row in df.iterrows()
            ]
            return {"runs": runs, "total_count": len(runs)}
        except Exception as e:
            return {"error": str(e), "runs": [], "total_count": 0}

    @mcp_server.tool
    def get_optimization_results(run_id: str) -> dict:
        """
        Get planogram recommendations for a specific optimization run.
        
        Args:
            run_id: The unique identifier of the optimization run (OPT-* format)
            
        Returns:
            Planogram recommendations including facings, changes, and profit metrics.
        """
        try:
            # Use opt_recommended_planogram table from new schema
            table = db_config.opt_planogram_table
            query = f"SELECT * FROM {table} WHERE optimization_run_id = %s"
            df = query_df(query, (run_id,))
            skus = df.to_dict(orient="records")
            
            # Calculate summary statistics
            summary = {}
            if not df.empty:
                ranged_df = df[df['is_ranged_recommended'] == True] if 'is_ranged_recommended' in df else df
                summary = {
                    "sku_count": len(df),
                    "skus_in_range": len(ranged_df),
                    "total_facings": ranged_df["recommended_facings"].sum() if "recommended_facings" in ranged_df else 0,
                    "total_weekly_profit": ranged_df["expected_margin_weekly"].sum() if "expected_margin_weekly" in ranged_df else 0,
                }
            
            return {
                "run_id": run_id,
                "skus": skus,
                "summary": summary
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def recommend_facings_changes(
        run_id: Optional[str] = None,
        change_type: Optional[str] = None,
        limit: int = 20
    ) -> dict:
        """
        Get prioritized SKU recommendations based on planogram optimization.
        
        Args:
            run_id: Optional - use latest run if not specified
            change_type: Filter by change type ('new', 'removed', 'increased', 'decreased')
            limit: Maximum number of recommendations to return
            
        Returns:
            Prioritized list of SKUs with facings changes, sorted by profit impact.
        """
        try:
            table = db_config.opt_planogram_table
            
            # Get latest run if not specified
            if not run_id:
                latest_query = f"""
                    SELECT optimization_run_id FROM {table} 
                    ORDER BY optimization_run_date DESC LIMIT 1
                """
                df = query_df(latest_query)
                if df.empty:
                    return {"error": "No optimization results found"}
                run_id = df.iloc[0]["optimization_run_id"]
            
            query = f"""
                SELECT sku_id, category_id, 
                       is_ranged_recommended, recommended_facings, facings_change,
                       change_from_current, expected_units_weekly, expected_margin_weekly
                FROM {table}
                WHERE optimization_run_id = %s
            """
            params = [run_id]
            
            if change_type:
                query += " AND change_from_current = %s"
                params.append(change_type)
            
            query += " ORDER BY expected_margin_weekly DESC LIMIT %s"
            params.append(limit)
            
            df = query_df(query, tuple(params))
            
            recommendations = []
            for _, row in df.iterrows():
                recommendations.append({
                    "sku_id": row["sku_id"],
                    "category_id": row["category_id"],
                    "recommended_facings": row["recommended_facings"],
                    "facings_change": row["facings_change"],
                    "change_type": row["change_from_current"],
                    "expected_weekly_units": row["expected_units_weekly"],
                    "expected_weekly_profit": row["expected_margin_weekly"],
                })
            
            return {
                "run_id": run_id,
                "recommendations": recommendations,
                "count": len(recommendations)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def get_category_insights(category_id: int) -> dict:
        """
        Analyze a product category across all optimization runs.
        
        Args:
            category_id: The category ID to analyze
            
        Returns:
            Category-level insights including SKU count, facings allocation,
            and trends across optimization runs.
        """
        try:
            table = db_config.opt_planogram_table
            query = f"""
                SELECT optimization_run_id, 
                       COUNT(*) as sku_count,
                       SUM(CASE WHEN is_ranged_recommended THEN 1 ELSE 0 END) as skus_ranged,
                       SUM(recommended_facings) as total_facings,
                       SUM(expected_margin_weekly) as total_weekly_profit,
                       MAX(optimization_run_date) as run_date
                FROM {table}
                WHERE category_id = %s
                GROUP BY optimization_run_id
                ORDER BY MAX(optimization_run_date) DESC
            """
            df = query_df(query, (category_id,))
            
            runs = df.to_dict(orient="records")
            
            return {
                "category_id": category_id,
                "optimization_history": runs,
                "total_runs": len(runs)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool  
    def compare_optimization_runs(run_id_1: str, run_id_2: str) -> dict:
        """
        Compare planogram recommendations between two optimization runs.
        
        Args:
            run_id_1: First run to compare
            run_id_2: Second run to compare
            
        Returns:
            Comparison showing changes in key metrics between runs.
        """
        try:
            table = db_config.opt_planogram_table
            
            def get_summary(rid):
                query = f"""
                    SELECT COUNT(*) as sku_count,
                           SUM(CASE WHEN is_ranged_recommended THEN 1 ELSE 0 END) as skus_ranged,
                           SUM(recommended_facings) as total_facings,
                           SUM(expected_margin_weekly) as total_weekly_profit
                    FROM {table}
                    WHERE optimization_run_id = %s
                """
                df = query_df(query, (rid,))
                if df.empty:
                    return None
                return df.iloc[0].to_dict()
            
            summary_1 = get_summary(run_id_1)
            summary_2 = get_summary(run_id_2)
            
            if not summary_1 or not summary_2:
                return {"error": "One or both optimization runs not found"}
            
            # Calculate differences
            changes = {}
            for key in summary_1:
                v1 = float(summary_1[key] or 0)
                v2 = float(summary_2[key] or 0)
                changes[key] = {
                    "run_1": v1,
                    "run_2": v2,
                    "change": v2 - v1,
                    "change_pct": ((v2 - v1) / v1 * 100) if v1 != 0 else 0
                }
            
            return {
                "run_id_1": run_id_1,
                "run_id_2": run_id_2,
                "comparison": changes
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def get_sku_details(sku_id: int) -> dict:
        """
        Get historical optimization data for a specific SKU.
        
        Args:
            sku_id: The SKU ID to look up
            
        Returns:
            All planogram recommendations for this SKU across optimization runs.
        """
        try:
            table = db_config.opt_planogram_table
            query = f"""
                SELECT * FROM {table}
                WHERE sku_id = %s
                ORDER BY optimization_run_date DESC
            """
            df = query_df(query, (sku_id,))
            
            return {
                "sku_id": sku_id,
                "history": df.to_dict(orient="records"),
                "total_entries": len(df)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp_server.tool
    def run_range_optimization(
        run_id: str,
        solver: str = "highs"
    ) -> dict:
        """
        Run the full range optimization process for submitted SKUs.
        
        Args:
            run_id: The optimization run ID (OPT-* format)
            solver: Solver to use ('highs' or 'fallback')
            
        Returns:
            Status of the optimization run including SKU count.
        """
        return run_range_optimization_logic(run_id, solver)

    log("✓ Registered 9 MCP tools")


def run_range_optimization_logic(
    run_id: str,
    solver: str = "highs"
) -> dict:
    """
    Core logic for running range optimization.
    Extracted from tool to allow direct API access.
    
    Reads from optimization_runs table and writes to opt_recommended_planogram.
    """
    try:
        import pandas as pd
        
        # Read from optimization_runs table
        runs_table = db_config.optimization_runs_table
        results_table = db_config.opt_planogram_table
        
        # 1. Fetch optimization run data
        query = f'SELECT * FROM {runs_table} WHERE "RUN_ID" = %s'
        df = query_df(query, (run_id,))
        
        if df.empty:
            return {
                "run_id": run_id,
                "solver": solver,
                "status": "error",
                "error": f"No optimization run data found for ID: {run_id}",
                "sku_count": 0
            }
        
        log(f"Found {len(df)} SKUs for run {run_id}")
        run_data = df.to_dict(orient="records")
        
        # 2. Transform SKU data from optimization_runs table format
        run_date = datetime.datetime.now().date().isoformat()
        timestamp = datetime.datetime.now().isoformat()
        
        log(f"Running range optimization for {len(run_data)} SKUs...")
        
        results_to_save = []
        for i, row in enumerate(run_data):
            # Get SKU identifiers - handle both uppercase and lowercase columns
            sku_id = row.get('SKU_ID') or row.get('sku_id') or f'SKU{i:04d}'
            sku_name = row.get('SKU_NAME') or row.get('sku_name') or 'Unknown Product'
            category = row.get('CATEGORY') or row.get('category') or 'Unknown'
            segment = row.get('SEGMENT') or row.get('segment') or 'Unknown'
            brand = row.get('BRAND') or row.get('brand') or 'Unknown'
            
            # Get metrics
            weekly_units = float(row.get('WEEKLY_UNITS') or row.get('weekly_units') or 70)
            unit_price = float(row.get('UNIT_PRICE') or row.get('unit_price') or 20.0)
            unit_cost = float(row.get('UNIT_COST') or row.get('unit_cost') or 10.0)
            current_facings = int(row.get('CURRENT_FACINGS') or row.get('current_facings') or 2)
            pack_width = int(row.get('PACK_WIDTH_MM') or row.get('pack_width_mm') or 100)
            is_must_stock = row.get('IS_MUST_STOCK') or row.get('is_must_stock') or False
            is_private_label = row.get('IS_PRIVATE_LABEL') or row.get('is_private_label') or False
            
            # Calculate profit metrics
            margin = unit_price - unit_cost
            expected_weekly_profit = weekly_units * margin
            
            # Simple optimization logic: allocate facings based on profit efficiency
            space_productivity = expected_weekly_profit / max(current_facings, 1)
            
            # Determine recommended facings (simple heuristic)
            if space_productivity > 50:
                recommended_facings = min(current_facings + 2, 6)
            elif space_productivity > 30:
                recommended_facings = min(current_facings + 1, 5)
            elif space_productivity > 15:
                recommended_facings = current_facings
            elif is_must_stock:
                recommended_facings = max(current_facings - 1, 1)
            else:
                recommended_facings = max(current_facings - 1, 0)
            
            # Determine if item is ranged and change type
            is_ranged = recommended_facings > 0
            facings_change = recommended_facings - current_facings
            
            if current_facings == 0 and recommended_facings > 0:
                change_type = "new"
            elif recommended_facings == 0 and current_facings > 0:
                change_type = "removed"
            elif facings_change > 0:
                change_type = "increased"
            elif facings_change < 0:
                change_type = "decreased"
            else:
                change_type = "no_change"
            
            # Create result aligned with opt_recommended_planogram schema
            # Include all fields needed for UI display
            results_to_save.append({
                "optimization_run_id": run_id,
                "store_id": None,  # Cluster-level optimization
                "planogram_cluster_id": 1,  # Default cluster
                "category_id": hash(category) % 1000,  # Simple hash for demo
                "sku_id": sku_id,
                # Include descriptive fields for UI grid display
                "sku_name": sku_name,
                "category": category,
                "segment": segment,
                "brand": brand,
                "current_facings": current_facings,
                "pack_width_mm": pack_width,
                "is_must_stock": is_must_stock,
                "is_private_label": is_private_label,
                # Optimization results
                "is_ranged_recommended": is_ranged,
                "recommended_facings": recommended_facings,
                "recommended_shelf_level": 3,  # Eye level default
                "recommended_position_order": i + 1,
                "expected_units_weekly": int(weekly_units),
                "expected_sales_value_weekly": round(weekly_units * unit_price, 2),
                "expected_margin_weekly": round(expected_weekly_profit, 2),
                "change_from_current": change_type,
                "facings_change": facings_change,
                "execution_difficulty": "low" if abs(facings_change) <= 1 else "medium" if abs(facings_change) <= 2 else "high",
                "optimization_run_date": run_date,
                "valid_from_date": run_date,
            })
        
        results_df = pd.DataFrame(results_to_save)
        
        # Check if table needs schema migration (has all required columns)
        from ..database import get_connection, create_table_from_dataframe, check_table_exists
        
        required_cols = ['sku_name', 'category', 'brand', 'current_facings']
        needs_migration = False
        
        if check_table_exists(results_table):
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'opt_recommended_planogram'")
                        existing_cols = [row[0] for row in cur.fetchall()]
                        needs_migration = not all(col in existing_cols for col in required_cols)
            except Exception as check_err:
                log(f"Error checking schema: {check_err}")
                needs_migration = True
        
        if needs_migration:
            log(f"Schema migration needed - dropping and recreating {results_table}...")
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"DROP TABLE IF EXISTS {results_table}")
                    conn.commit()
                log("Old table dropped successfully")
            except Exception as drop_err:
                log(f"Error dropping table: {drop_err}")
        
        # Try to insert results
        try:
            bulk_insert(results_table, results_df, overwrite=False)
        except Exception as insert_err:
            err_str = str(insert_err).lower()
            if "does not exist" in err_str or "column" in err_str:
                # Schema mismatch - recreate table
                log(f"Schema mismatch detected on insert, recreating {results_table} table...")
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"DROP TABLE IF EXISTS {results_table}")
                    conn.commit()
                create_table_from_dataframe(results_table, results_df)
                bulk_insert(results_table, results_df, overwrite=False)
            else:
                raise
        
        return {
            "run_id": run_id,
            "solver": solver,
            "status": "success",
            "sku_count": len(results_to_save),
            "method": "range_optimizer_mcp"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "run_id": run_id,
            "solver": solver,
            "status": "error",
            "error": str(e),
            "sku_count": 0
        }


