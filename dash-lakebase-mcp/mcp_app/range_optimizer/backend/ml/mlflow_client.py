"""
MLflow Model Serving Client

This module provides a client for calling Databricks MLflow Model Serving endpoints.

Schema Alignment:
- Input: SKU_ID, SKU_NAME, CURRENT_FACINGS (features auto-fetched from Feature Store)
- Output: RECOMMENDED_FACINGS, FACINGS_CHANGE, CHANGE_TYPE, EXPECTED_WEEKLY_PROFIT, etc.
"""

import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from databricks.sdk import WorkspaceClient


class MLflowModelClient:
    """Client for calling MLflow model serving endpoints in Databricks"""

    def __init__(self, endpoint_name: str = "range-optimizer-model"):
        """
        Initialize the MLflow model client.

        Args:
            endpoint_name: Name of the MLflow model serving endpoint
        """
        self.endpoint_name = endpoint_name
        self.workspace_client = WorkspaceClient()
        self.base_url = self.workspace_client.config.host
        self.token = self.workspace_client.config.token

    def predict(self, forecast_data: pd.DataFrame) -> pd.DataFrame:
        """
        Call the MLflow model serving endpoint to get range optimization predictions.

        Args:
            forecast_data: DataFrame with SKU data (SKU_ID required, features auto-fetched)

        Returns:
            DataFrame with optimization results
        """
        # Prepare the request payload
        data_records = forecast_data.to_dict(orient='records')

        payload = {
            "dataframe_records": data_records
        }

        # Construct the endpoint URL
        endpoint_url = f"{self.base_url}/serving-endpoints/{self.endpoint_name}/invocations"

        # Make the request
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                endpoint_url,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()

            # Parse the response
            predictions = response.json()

            # Convert predictions back to DataFrame
            if isinstance(predictions, dict) and "predictions" in predictions:
                result_df = pd.DataFrame(predictions["predictions"])
            elif isinstance(predictions, list):
                result_df = pd.DataFrame(predictions)
            else:
                result_df = pd.DataFrame([predictions])

            return result_df

        except requests.exceptions.RequestException as e:
            raise Exception(f"Error calling MLflow endpoint: {str(e)}")

    def check_endpoint_status(self) -> Dict:
        """
        Check the status of the MLflow model serving endpoint.

        Returns:
            Dictionary with endpoint status information
        """
        endpoint_url = f"{self.base_url}/api/2.0/serving-endpoints/{self.endpoint_name}"

        headers = {
            "Authorization": f"Bearer {self.token}",
        }

        try:
            response = requests.get(endpoint_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status": "unavailable"}


class FallbackOptimizer:
    """
    Fallback optimizer that uses local computation when MLflow endpoint is unavailable.
    This is useful for development and testing.
    """

    @staticmethod
    def optimize(forecast_data: pd.DataFrame) -> pd.DataFrame:
        """
        Perform range optimization locally as a fallback.

        Args:
            forecast_data: DataFrame with SKU forecast data

        Returns:
            DataFrame with optimization results
        """
        from .stock_optimizer import StockOptimizer, OptimizationConfig

        config = OptimizationConfig()
        optimizer = StockOptimizer(config=config)
        return optimizer.optimize_inventory(forecast_data)


class HybridStockOptimizer:
    """
    Hybrid optimizer that tries to use MLflow endpoint first,
    falls back to local computation if endpoint is unavailable.
    """

    def __init__(
        self,
        endpoint_name: str = "range-optimizer-model",
        use_fallback: bool = True
    ):
        """
        Initialize the hybrid optimizer.

        Args:
            endpoint_name: Name of the MLflow model serving endpoint
            use_fallback: Whether to use local fallback if endpoint fails
        """
        self.endpoint_name = endpoint_name
        self.use_fallback = use_fallback
        self.mlflow_client: Optional[MLflowModelClient] = None

    def _get_mlflow_client(self) -> MLflowModelClient:
        """Get or create MLflow client"""
        if self.mlflow_client is None:
            self.mlflow_client = MLflowModelClient(self.endpoint_name)
        return self.mlflow_client

    def optimize(self, forecast_data: pd.DataFrame) -> tuple[pd.DataFrame, str]:
        """
        Optimize facings using MLflow endpoint or local fallback.

        Args:
            forecast_data: DataFrame with SKU forecast data

        Returns:
            Tuple of (optimized DataFrame, method used)
            method will be one of: "mlflow", "fallback", "error"
        """
        # First, try MLflow endpoint
        try:
            client = self._get_mlflow_client()

            # Check endpoint status
            status = client.check_endpoint_status()
            if "error" in status:
                raise Exception(f"Endpoint unavailable: {status['error']}")

            # Call the endpoint
            result_df = client.predict(forecast_data)
            return result_df, "mlflow"

        except Exception as mlflow_error:
            print(f"⚠️  MLflow endpoint failed: {str(mlflow_error)}")

            if not self.use_fallback:
                raise mlflow_error

            # Fall back to local computation
            print("→ Using local fallback optimization...")
            try:
                result_df = FallbackOptimizer.optimize(forecast_data)
                return result_df, "fallback"
            except Exception as fallback_error:
                print(f"❌ Fallback optimization failed: {str(fallback_error)}")
                raise Exception(
                    f"Both MLflow and fallback failed. "
                    f"MLflow: {str(mlflow_error)}, Fallback: {str(fallback_error)}"
                )

    def get_optimization_summary(self, optimized_df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics from optimization results.
        
        Aligned with the new schema output columns.
        """
        summary = {
            'total_skus': len(optimized_df),
            'service_level': 0.95,  # Default
        }
        
        # Handle both old and new column names
        if 'RECOMMENDED_FACINGS' in optimized_df.columns:
            summary['total_facings'] = int(optimized_df['RECOMMENDED_FACINGS'].sum())
        elif 'OPTIMAL_ORDER_QTY' in optimized_df.columns:  # Legacy
            summary['total_facings'] = int(optimized_df['OPTIMAL_ORDER_QTY'].sum())
        
        if 'IS_RANGED' in optimized_df.columns:
            summary['skus_ranged'] = int(optimized_df['IS_RANGED'].sum())
        
        if 'EXPECTED_WEEKLY_PROFIT' in optimized_df.columns:
            summary['total_weekly_profit'] = float(optimized_df['EXPECTED_WEEKLY_PROFIT'].sum())
        elif 'EXPECTED_ANNUAL_PROFIT' in optimized_df.columns:  # Legacy
            summary['total_annual_profit'] = float(optimized_df['EXPECTED_ANNUAL_PROFIT'].sum())
        
        if 'SPACE_PRODUCTIVITY' in optimized_df.columns:
            summary['avg_space_productivity'] = float(optimized_df['SPACE_PRODUCTIVITY'].mean())
        elif 'TURNOVER_RATE' in optimized_df.columns:  # Legacy
            summary['avg_turnover_rate'] = float(optimized_df['TURNOVER_RATE'].mean())
        
        if 'CHANGE_TYPE' in optimized_df.columns:
            summary['skus_increased'] = len(optimized_df[optimized_df['CHANGE_TYPE'] == 'increased'])
            summary['skus_decreased'] = len(optimized_df[optimized_df['CHANGE_TYPE'] == 'decreased'])
            summary['skus_new'] = len(optimized_df[optimized_df['CHANGE_TYPE'] == 'new'])
            summary['skus_removed'] = len(optimized_df[optimized_df['CHANGE_TYPE'] == 'removed'])
        
        if 'SERVICE_LEVEL' in optimized_df.columns and len(optimized_df) > 0:
            summary['service_level'] = float(optimized_df['SERVICE_LEVEL'].iloc[0])
        
        return summary
