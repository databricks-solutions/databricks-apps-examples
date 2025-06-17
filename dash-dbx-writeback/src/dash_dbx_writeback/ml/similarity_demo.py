"""Product similarity demo using sentence-transformers.

This offline script generates text embeddings for ``PRODUCT_NAME`` and prints
out the three most similar products for each item in the sample data.  It also
saves the embeddings to ``data/product_embeddings.parquet`` so they can be
loaded by a vector search service later.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from ..data.sample_product_data import INITIAL_DATA

EMB_PATH = Path(__file__).resolve().parent.parent / "data" / "product_embeddings.parquet"


def main():
    df = pd.DataFrame(INITIAL_DATA)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(df["PRODUCT_NAME"].tolist(), show_progress_bar=False)

    sim = cosine_similarity(embeddings)

    for i, name in enumerate(df["PRODUCT_NAME"]):
        top_idx = np.argsort(-sim[i])[1:4]  # exclude self
        similar = df.iloc[top_idx]["PRODUCT_NAME"].tolist()
        print(f"{name} → {similar}")

    # Save embeddings
    out_df = df[["SELL_ID", "PRODUCT_NAME"]].assign(embedding=list(embeddings))
    EMB_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(EMB_PATH, index=False)
    print(f"✔ Saved embeddings to {EMB_PATH.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main() 