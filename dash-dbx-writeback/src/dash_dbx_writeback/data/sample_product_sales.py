import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta

def generate_time_series_data(
    products: List[Dict[str, Any]],
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    freq: str = "D",
    base_min: int = 20,
    base_max: int = 100,
    trend: float = 0.05,
    seasonality_amplitude: int = 15,
    noise_std: int = 8,
) -> pd.DataFrame:
    """
    Generate a realistic time series sales dataset for each product.

    Args:
        products: List of product dicts (e.g., INITIAL_DATA)
        start_date: Start date for the time series (YYYY-MM-DD)
        end_date: End date for the time series (YYYY-MM-DD)
        freq: Frequency of data points ('D' for daily)
        base_min: Minimum base sales per product
        base_max: Maximum base sales per product
        trend: Linear trend per year (as a fraction of base)
        seasonality_amplitude: Amplitude of seasonal effect
        noise_std: Standard deviation of random noise

    Returns:
        pd.DataFrame: DataFrame with columns:
            ['SELL_ID', 'DATE', 'SALES', ...product columns]
    """
    date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
    all_rows = []
    rng = np.random.default_rng(42)

    for product in products:
        base = rng.integers(base_min, base_max)
        for i, date in enumerate(date_range):
            # Add linear trend
            trend_factor = 1 + trend * (i / len(date_range))
            # Add seasonality (e.g., weekly pattern)
            seasonality = 1 + seasonality_amplitude * np.sin(2 * np.pi * (date.timetuple().tm_yday) / 365)
            # Add random noise
            noise = rng.normal(0, noise_std)
            sales = max(0, int(base * trend_factor + seasonality + noise))
            row = {
                "SELL_ID": product["SELL_ID"],
                "DATE": date,
                "SALES": sales,
                **product,
            }
            all_rows.append(row)

    return pd.DataFrame(all_rows)