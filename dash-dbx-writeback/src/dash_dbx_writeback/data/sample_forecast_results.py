"""Dummy forecast results generated for demo purposes.

This file is created automatically by ``ml/catboost_forecast.py``.  It is
provided here as a fallback so the app has something to display even before you
run the ML scripts.
"""

import datetime
from typing import List, Dict, Any

from .sample_product_data import INITIAL_DATA


def generate_dummy_results() -> List[Dict[str, Any]]:
    """Attach random predictions to INITIAL_DATA and return list of dicts."""
    import random

    rng = random.Random(0)
    results = []
    forecast_id = "DEMO-STATIC"
    timestamp = datetime.datetime.utcnow().isoformat()
    for row in INITIAL_DATA:
        record = dict(row)
        record["PREDICTED_UNITS"] = rng.randint(100, 800)
        record["PREDICTED_REVENUE"] = round(record["PREDICTED_UNITS"] * rng.uniform(3.0, 9.0), 2)
        record["FORECAST_ID"] = forecast_id
        record["SUBMISSION_TIMESTAMP"] = timestamp
        results.append(record)
    return results


DUMMY_FORECAST_RESULTS: List[Dict[str, Any]] = generate_dummy_results() 