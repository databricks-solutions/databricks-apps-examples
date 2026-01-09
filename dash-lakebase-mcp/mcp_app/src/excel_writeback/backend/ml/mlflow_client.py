"""
MLflow Model Serving Client

This module provides a client for calling Databricks MLflow Model Serving endpoints.
"""

import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from databricks.sdk import WorkspaceClient


class MLflowModelClient:
    """Client for calling MLflow model serving endpoints in Databricks"""

    def __init__(self, endpoint_name: str = "stock-optimization-model"):
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
        Call the MLflow model serving endpoint to get stock optimization predictions.

        Args:
            forecast_data: DataFrame with forecast data

        Returns:
            DataFrame with optimization results
        """
        # Prepare the request payload
        # Convert DataFrame to the format expected by the model
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
        Perform stock optimization locally as a fallback.

        Args:
            forecast_data: DataFrame with forecast data

        Returns:
            DataFrame with optimization results
        """
        from .stock_optimizer import StockOptimizer, OptimizationConfig

        config = OptimizationConfig()
        optimizer = StockOptimizer(config=config)
        return optimizer.optimize_inventory(forecast_data)


class HybridStockOptimizer:
    """
    Hybrid stock optimizer that tries to use MLflow endpoint first,
    falls back to local computation if endpoint is unavailable.
    """

    def __init__(
        self,
        endpoint_name: str = "stock-optimization-model",
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
        Optimize inventory using MLflow endpoint or local fallback.

        Args:
            forecast_data: DataFrame with forecast data

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
        """Generate summary statistics from optimization results"""
        return {
            'total_products': len(optimized_df),
            'total_optimal_stock_units': float(optimized_df['OPTIMAL_ORDER_QTY'].sum()),
            'total_safety_stock_units': float(optimized_df['SAFETY_STOCK'].sum()),
            'total_max_stock_units': float(optimized_df['MAX_STOCK_LEVEL'].sum()),
            'total_annual_cost': float(optimized_df['TOTAL_ANNUAL_COST'].sum()),
            'total_annual_revenue': float(optimized_df['EXPECTED_ANNUAL_REVENUE'].sum()),
            'total_annual_profit': float(optimized_df['EXPECTED_ANNUAL_PROFIT'].sum()),
            'avg_turnover_rate': float(optimized_df['TURNOVER_RATE'].mean()),
            'service_level': float(optimized_df['SERVICE_LEVEL'].iloc[0]) if len(optimized_df) > 0 else 0.95,
        }
