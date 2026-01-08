"""
Generate a clean, left-to-right architecture diagram using Graphviz DOT directly.

Why DOT (vs diagrams/matplotlib)?
- Much tighter control over layout (rank ordering, spacing, straight boxes)
- Reliable image embedding (PNG icons) for Unity Catalog and Delta Lake
"""

from __future__ import annotations

import os
import subprocess


def _q(s: str) -> str:
    """Quote a string for DOT."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _html_label(title: str, subtitle: str | None = None, image_path: str | None = None) -> str:
    """Create an HTML-like label with optional image."""
    subtitle_row = (
        f'<TR><TD><FONT POINT-SIZE="10" COLOR="#424242">{subtitle}</FONT></TD></TR>'
        if subtitle
        else ""
    )
    img_row = (
        f'<TR><TD FIXEDSIZE="TRUE" WIDTH="140" HEIGHT="48"><IMG SRC={_q(image_path)} SCALE="TRUE"/></TD></TR>'
        if image_path
        else ""
    )
    return (
        "<<TABLE BORDER=\"0\" CELLBORDER=\"0\" CELLPADDING=\"2\" CELLSPACING=\"0\">"
        f"{img_row}"
        f"<TR><TD><B>{title}</B></TD></TR>"
        f"{subtitle_row}"
        "</TABLE>>"
    )


def main() -> None:
    # Resolve paths relative to this script so output is stable regardless of cwd
    here = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(here, "src", "dash_dbx_writeback", "assets")
    os.makedirs(assets_dir, exist_ok=True)

    logos_dir = os.path.join(assets_dir, "diagram_logos")
    delta_logo_png = os.path.join(logos_dir, "delta-lake-logo.png")
    uc_logo_png = os.path.join(logos_dir, "uc-logo.png")

    out_png = os.path.join(assets_dir, "architecture.png")
    out_dot = os.path.join(assets_dir, "architecture.dot")

    # Visual style
    node_style = 'shape=box style="rounded" penwidth=2 fontname="Helvetica" fontsize=12'
    edge_style = 'fontname="Helvetica" fontsize=10 color="#1A73E8"'

    dot = f"""
digraph G {{
  graph [
    rankdir=LR
    bgcolor="white"
    fontname="Helvetica"
    fontsize=20
    labelloc="t"
    labeljust="c"
    label="Coles Inventory Intelligence Architecture"
    compound=true
    newrank=true
    splines=ortho
    nodesep=0.55
    ranksep=0.75
    pad=0.25
  ];

  node [{node_style}];
  edge [{edge_style}];

  user [label={_html_label("User")} color="#1A73E8"];

  subgraph cluster_databricks {{
    label="Databricks";
    color="#B0BEC5";
    style="rounded";

    subgraph cluster_apps {{
      label="Databricks Apps";
      color="#FF3621";
      style="rounded";
      dash_app [label={_html_label("Databricks App", "Dash + DMC")} color="#FF3621"];
      mcp_app  [label={_html_label("Databricks App", "MCP Server")} color="#FF3621"];
    }}

    subgraph cluster_data {{
      label="Data Layer";
      color="#00A972";
      style="rounded";

      lakebase [label={_html_label("Lakebase", "PostgreSQL")} color="#00A972"];

      subgraph cluster_delta {{
        label="Delta Lake";
        color="#00A972";
        style="rounded";
        delta_lake [label={_html_label("Delta Lake", None, delta_logo_png)} color="#00A972"];
        feature_store_delta [label={_html_label("Feature Store", "Delta")} color="#00A972"];
        classic_ml_delta    [label={_html_label("Classic ML Model", "Delta")} color="#00A972"];
      }}

      subgraph cluster_uc {{
        label="Unity Catalog";
        color="#00A972";
        style="rounded";
        unity_catalog [label={_html_label("Unity Catalog", None, uc_logo_png)} color="#00A972"];
        uc_feature_store [label={_html_label("Feature Store", "Registered")} color="#00A972"];
        uc_classic_ml    [label={_html_label("Classic ML Model", "Registered")} color="#00A972"];
      }}
    }}

    subgraph cluster_serving {{
      label="Model Serving";
      color="#1A73E8";
      style="rounded";
      llm_endpoint [label={_html_label("LLM Endpoint", "Llama 3 70B")} color="#1A73E8"];
      opt_endpoint [label={_html_label("Classic ML Endpoint", "Stock Optimizer")} color="#1A73E8"];
    }}
  }}

  // Core interaction flow (left -> right)
  user -> dash_app [xlabel="Interacts"];
  dash_app -> mcp_app [xlabel="Insights / Chat API"];

  // Data access
  dash_app -> lakebase [xlabel="Read/Write" color="#00A972"];
  mcp_app  -> lakebase [xlabel="Query Context" color="#00A972"];

  // Feature store + model stored in Delta and registered in UC
  lakebase -> feature_store_delta [xlabel="Feature Store" color="#00A972"];
  delta_lake -> feature_store_delta [style=dashed color="#00A972" xlabel="Delta"];
  delta_lake -> classic_ml_delta    [style=dashed color="#00A972" xlabel="Delta"];

  feature_store_delta -> uc_feature_store [style=dashed color="#00A972" xlabel="Sync/Register"];
  classic_ml_delta    -> uc_classic_ml    [style=dashed color="#00A972" xlabel="Register"];

  // Deploy serving endpoint from UC-registered model
  uc_classic_ml -> opt_endpoint [style=dashed xlabel="Deploy"];

  // Tool use into Model Serving
  mcp_app -> llm_endpoint [xlabel="Tool Use"];
  mcp_app -> opt_endpoint [xlabel="Tool Use"];

  // App can invoke optimization via endpoint too
  dash_app -> opt_endpoint [style=dashed xlabel="Run Optimization"];

  // Layout helpers (stable across clusters): invisible edges to encourage columns
  user -> dash_app [style=invis weight=50];
  dash_app -> lakebase [style=invis weight=50];
  lakebase -> llm_endpoint [style=invis weight=20];
}}
""".strip()

    with open(out_dot, "w", encoding="utf-8") as f:
        f.write(dot + "\n")

    subprocess.run(["dot", "-Tpng", out_dot, "-o", out_png], check=True)
    print(f"✓ Wrote {out_png}")


if __name__ == "__main__":
    main()

