"""CatBoost regression demo for Excel the Dash Way.

This script trains a CatBoostRegressor on the categorical product attributes
found in ``sample_product_data.INITIAL_DATA`` and produces a dummy forecast
(``PREDICTED_UNITS``) suitable for seeding the results page.

Running the file will:
1. Create a DataFrame from the sample product records.
2. Synthesize a numeric target (units) so the demo can run fully offline.
3. Fit a CatBoostRegressor (fast ‑ < 1 s on the sample data).
4. Generate predictions for every product.
5. Save the predictions to ``data/dummy_forecast_results.csv`` and print the
   RMSE plus top-5 feature importances.

If you set the environment variables required by ``workspace_client`` the
``--write-db`` flag will also write the results to your Databricks table
``<catalog>.<schema>.forecast_results`` via the SQL connector, allowing the
Dash *Results* page to pick them up immediately.
"""

from __future__ import annotations

import argparse
import datetime
import random
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool

from ..config.unity_catalog import get_full_table_name
from ..config.workspace_client import get_connection
from ..data.sample_product_data import INITIAL_DATA

OUTPUT_CSV = Path(__file__).resolve().parent.parent / "data" / "dummy_forecast_results.csv"


def generate_target(n: int) -> List[int]:
    """Create a reproducible pseudo-random target series.«""""
    rng = random.Random(42)
    return [rng.randint(50, 500) for _ in range(n)]


def main(write_db: bool = False):
    df = pd.DataFrame(INITIAL_DATA)
    df["TARGET_UNITS"] = generate_target(len(df))

    # Train / test split (80/20)
    train_df = df.sample(frac=0.8, random_state=1)
    test_df = df.drop(train_df.index)

    features = [c for c in df.columns if c not in {"TARGET_UNITS"}]
    cat_features = list(range(len(features)))  # all are categorical indices

    train_pool = Pool(train_df[features], train_df["TARGET_UNITS"], cat_features=cat_features)
    test_pool = Pool(test_df[features], test_df["TARGET_UNITS"], cat_features=cat_features)

    model = CatBoostRegressor(iterations=250, depth=6, learning_rate=0.1, loss_function="RMSE", verbose=False)
    model.fit(train_pool)

    preds = model.predict(df[features])
    df["PREDICTED_UNITS"] = preds.round().astype(int)

    rmse = model.eval_metrics(test_pool, ["RMSE"])["RMSE"][-1]
    feat_imp = model.get_feature_importance(type="FeatureImportance")
    ordered = sorted(zip(features, feat_imp), key=lambda t: t[1], reverse=True)[:5]

    print("RMSE:", rmse)
    print("Top-5 features:")
    for name, imp in ordered:
        print(f"  {name:<20} {imp:0.1f}")

    # Build results table (matches Results grid expectation)
    forecast_id = f"DEMO-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    results = df.assign(FORECAST_ID=forecast_id, SUBMISSION_TIMESTAMP=datetime.datetime.utcnow().isoformat())

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT_CSV, index=False)
    print(f"✔ Saved results to {OUTPUT_CSV.relative_to(Path.cwd())}")

    if write_db:
        try:
            conn = get_connection()
            table_name = get_full_table_name("forecast_results")
            from ..callbacks.tables import insert_overwrite_table, ensure_table_exists

            ensure_table_exists(table_name, results, conn)
            insert_overwrite_table(table_name=table_name, df=results, conn=conn, overwrite=False)
            print(f"✔ Written {len(results)} rows to {table_name}")
        except Exception as exc:
            print("✗ Failed to write to Databricks:", exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CatBoost demo forecast")
    parser.add_argument("--write-db", action="store_true", help="Also write results to Databricks table")
    args = parser.parse_args()
    main(write_db=args.write_db) 