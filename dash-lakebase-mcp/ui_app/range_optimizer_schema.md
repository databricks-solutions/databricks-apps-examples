# Range Optimizer: Complete Schema & Data Model

## Overview

This document defines a complete, production-ready data model for a supermarket Range Optimizer system. It follows a **star schema** pattern optimized for both transactional operations (loading, updating rules) and analytical queries (demand modeling, optimization preparation).

All tables are designed to be implemented in a **Lakehouse** (Delta/Iceberg) with support for time-travel, ACID transactions, and efficient analytics.

---

## Core Dimensional Tables

### 1. `dim_sku`

**Purpose:** Master product dimension.

**Grain:** One row per unique SKU (product).

```sql
CREATE TABLE dim_sku (
  sku_id BIGINT PRIMARY KEY,
  gtin_ean BIGINT UNIQUE,
  sku_name VARCHAR(255) NOT NULL,
  brand_id BIGINT NOT NULL,
  manufacturer_id BIGINT NOT NULL,
  category_id BIGINT NOT NULL,
  subcategory_id BIGINT,
  segment VARCHAR(50),
  pack_size DECIMAL(10,2),
  pack_size_uom VARCHAR(20), -- 'g', 'ml', 'units', etc.
  case_pack_qty INT,
  pack_width_mm DECIMAL(10,2),
  pack_depth_mm DECIMAL(10,2),
  pack_height_mm DECIMAL(10,2),
  pack_type VARCHAR(50), -- 'box', 'bottle', 'pouch', etc.
  shelf_life_days INT,
  is_private_label BOOLEAN DEFAULT FALSE,
  is_chilled BOOLEAN DEFAULT FALSE,
  is_frozen BOOLEAN DEFAULT FALSE,
  sku_status VARCHAR(20), -- 'active', 'discontinued', 'new'
  launch_date DATE,
  discontinue_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE INDEX idx_sku_category ON dim_sku(category_id);
CREATE INDEX idx_sku_brand ON dim_sku(brand_id);
CREATE INDEX idx_sku_status ON dim_sku(sku_status);
```

**Example rows:**

| sku_id | sku_name | brand_id | category_id | pack_size | pack_width_mm | is_private_label |
|--------|----------|----------|-------------|-----------|---------------|------------------|
| 1001 | Crispy Flakes 500g | 101 | 51 | 500 | 180 | false |
| 1002 | Value Cereal 750g | 102 | 5 | 750 | 200 | true |
| 1003 | Organic Oats 400g | 103 | 52 | 400 | 165 | false |

---

### 2. `dim_store`

**Purpose:** Store master dimension.

**Grain:** One row per physical store.

```sql
CREATE TABLE dim_store (
  store_id BIGINT PRIMARY KEY,
  store_name VARCHAR(255) NOT NULL,
  store_code VARCHAR(50) UNIQUE NOT NULL,
  store_format VARCHAR(50), -- 'hypermarket', 'supermarket', 'convenience', etc.
  store_size_sqm INT,
  region_id BIGINT,
  region_name VARCHAR(100),
  city VARCHAR(100),
  postcode VARCHAR(20),
  country VARCHAR(50),
  affluence_segment VARCHAR(50), -- 'low', 'medium', 'high'
  demographic_profile VARCHAR(100), -- 'families', 'students', 'retirees', etc.
  opening_date DATE,
  closing_date DATE,
  planogram_cluster_id BIGINT, -- FK to cluster; multiple stores share one planogram
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE INDEX idx_store_cluster ON dim_store(planogram_cluster_id);
CREATE INDEX idx_store_region ON dim_store(region_id);
CREATE INDEX idx_store_format ON dim_store(store_format);
```

**Example rows:**

| store_id | store_name | store_format | city | planogram_cluster_id |
|----------|------------|--------------|------|----------------------|
| 2001 | Coles Docklands | supermarket | Melbourne | 10 |
| 2002 | Coles Spencer St | supermarket | Melbourne | 10 |
| 2003 | Coles Brisbane North | supermarket | Brisbane | 20 |

---

### 3. `dim_category`

**Purpose:** Category hierarchy and metadata.

**Grain:** One row per category (supports multi-level hierarchy via category_id and parent_category_id).

```sql
CREATE TABLE dim_category (
  category_id BIGINT PRIMARY KEY,
  category_name VARCHAR(255) NOT NULL UNIQUE,
  department VARCHAR(100), -- 'Grocery', 'Fresh', 'Non-Food', etc.
  parent_category_id BIGINT, -- For hierarchy; NULL for top-level
  category_role VARCHAR(50), -- 'destination', 'routine', 'convenience', 'seasonal'
  space_priority INT, -- 1=highest, increasing = lower
  is_chill_category BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

INSERT INTO dim_category VALUES
(5, 'Breakfast Cereals', 'Grocery', NULL, 'routine', 3, FALSE, NOW(), NOW()),
(51, 'Kids Cereals', 'Grocery', 5, 'routine', 3, FALSE, NOW(), NOW()),
(52, 'Adult Health Cereals', 'Grocery', 5, 'destination', 2, FALSE, NOW(), NOW());
```

---

### 4. `dim_brand`

**Purpose:** Brand master.

**Grain:** One row per brand.

```sql
CREATE TABLE dim_brand (
  brand_id BIGINT PRIMARY KEY,
  brand_name VARCHAR(255) NOT NULL UNIQUE,
  manufacturer_id BIGINT,
  brand_country VARCHAR(50),
  is_private_label BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

---

### 5. `dim_time`

**Purpose:** Time dimension for time-series analysis (optional but useful for efficient queries).

**Grain:** One row per week (or day, depending on granularity).

```sql
CREATE TABLE dim_time (
  time_id INT PRIMARY KEY,
  date_key DATE NOT NULL UNIQUE,
  week_start_date DATE,
  week_end_date DATE,
  month_start_date DATE,
  month INT,
  quarter INT,
  year INT,
  is_holiday BOOLEAN DEFAULT FALSE,
  holiday_name VARCHAR(100)
);
```

---

## Core Fact Tables

### 6. `fact_sales_weekly`

**Purpose:** Historical sales data; core input for demand modeling.

**Grain:** Store × SKU × Week.

**Partitioning:** By `week_start_date` (or month for older data).

```sql
CREATE TABLE fact_sales_weekly (
  sale_id BIGINT PRIMARY KEY,
  store_id BIGINT NOT NULL,
  sku_id BIGINT NOT NULL,
  week_start_date DATE NOT NULL,
  units_sold INT DEFAULT 0,
  net_sales_value DECIMAL(15,2) DEFAULT 0,
  regular_price DECIMAL(10,2),
  promo_price DECIMAL(10,2),
  promo_flag BOOLEAN DEFAULT FALSE,
  promo_type VARCHAR(50), -- 'price_discount', 'bogo', 'bundle', etc.
  promo_discount_pct DECIMAL(5,2), -- e.g., 20 for 20% off
  on_display_flag BOOLEAN DEFAULT FALSE, -- on endcap or secondary
  on_promotion_flag BOOLEAN DEFAULT FALSE,
  availability_rate DECIMAL(5,2), -- 0-100, % of day in stock
  out_of_stock_days INT, -- number of days OOS in week
  stock_at_week_start INT,
  stock_at_week_end INT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (sale_id),
  CONSTRAINT fk_store FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES dim_sku(sku_id)
);

CREATE INDEX idx_sales_store_week ON fact_sales_weekly(store_id, week_start_date);
CREATE INDEX idx_sales_sku_week ON fact_sales_weekly(sku_id, week_start_date);
```

**Example rows:**

| store_id | sku_id | week_start_date | units_sold | net_sales_value | promo_flag | availability_rate |
|----------|--------|-----------------|------------|-----------------|------------|-------------------|
| 2001 | 1001 | 2025-12-01 | 120 | 840 | false | 98 |
| 2001 | 1002 | 2025-12-01 | 85 | 510 | true | 95 |
| 2001 | 1001 | 2025-12-08 | 145 | 1015 | true | 100 |

---

### 7. `fact_planogram_current`

**Purpose:** Current shelf layout (as-is state).

**Grain:** Store × Category × SKU (one row per ranged SKU in a category at a store/cluster).

```sql
CREATE TABLE fact_planogram_current (
  planogram_id BIGINT PRIMARY KEY,
  store_id BIGINT NOT NULL,
  category_id BIGINT NOT NULL,
  sku_id BIGINT NOT NULL,
  shelf_id VARCHAR(50), -- e.g., 'Gondola_3_SideA'
  shelf_level INT, -- 1=bottom, 5=top (example 5-shelf unit)
  position_order INT, -- left-to-right position on shelf level
  facings_horizontal INT, -- number of items across
  facings_vertical INT, -- number of items high
  facings_depth INT, -- number of items deep
  total_facings INT, -- = horizontal * vertical * depth
  effective_width_mm INT, -- (facings_horizontal * pack_width)
  effective_height_mm INT, -- (facings_vertical * pack_height)
  start_position_mm INT, -- position from left edge of shelf
  end_position_mm INT, -- start + effective_width
  is_eye_level BOOLEAN, -- TRUE if shelf_level in [3,4] (eye level typically)
  last_updated_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (planogram_id),
  CONSTRAINT fk_store FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
  CONSTRAINT fk_category FOREIGN KEY (category_id) REFERENCES dim_category(category_id),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES dim_sku(sku_id)
);

CREATE INDEX idx_planogram_store_cat ON fact_planogram_current(store_id, category_id);
CREATE INDEX idx_planogram_sku ON fact_planogram_current(sku_id);
```

**Example rows:**

| planogram_id | store_id | category_id | sku_id | shelf_id | shelf_level | facings_horizontal | total_facings | is_eye_level |
|--------------|----------|-------------|--------|----------|-------------|-------------------|----------------|--------------|
| 3001 | 2001 | 5 | 1001 | Gondola_3_A | 3 | 4 | 12 | true |
| 3002 | 2001 | 5 | 1002 | Gondola_3_A | 3 | 3 | 9 | true |
| 3003 | 2001 | 5 | 1003 | Gondola_3_A | 2 | 2 | 6 | false |

---

### 8. `fact_shelf_inventory`

**Purpose:** Physical shelf space constraints and current utilization (optional but useful for constraint checking).

**Grain:** Store × Shelf segment × Category.

```sql
CREATE TABLE fact_shelf_inventory (
  shelf_inventory_id BIGINT PRIMARY KEY,
  store_id BIGINT NOT NULL,
  category_id BIGINT NOT NULL,
  shelf_id VARCHAR(50),
  shelf_level INT,
  total_width_mm INT,
  total_height_mm INT,
  total_depth_mm INT,
  max_weight_kg INT,
  is_chilled BOOLEAN DEFAULT FALSE,
  current_utilized_width_mm INT, -- sum of effective_width from planogram
  current_available_width_mm INT, -- total - utilized
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (shelf_inventory_id),
  CONSTRAINT fk_store FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
  CONSTRAINT fk_category FOREIGN KEY (category_id) REFERENCES dim_category(category_id)
);
```

---

## Configuration & Rules Tables

### 9. `cfg_range_constraints`

**Purpose:** Store business rules for range breadth, facings, and assortment.

**Grain:** Store (or Cluster) × Category.

```sql
CREATE TABLE cfg_range_constraints (
  constraint_id BIGINT PRIMARY KEY,
  store_id BIGINT, -- NULL if applies to cluster
  planogram_cluster_id BIGINT,
  category_id BIGINT NOT NULL,
  min_range_size INT, -- minimum number of SKUs
  max_range_size INT, -- maximum number of SKUs
  min_facings_per_sku INT DEFAULT 1,
  max_facings_per_sku INT DEFAULT 99,
  min_private_label_share DECIMAL(5,2), -- e.g., 20.0 for 20%
  max_any_brand_share DECIMAL(5,2), -- e.g., 40.0 for max 40%
  min_eye_level_share DECIMAL(5,2), -- e.g., 50.0 for min 50% on eye level
  forced_include_skus VARCHAR(1000), -- comma-separated sku_ids that must be included
  forced_exclude_skus VARCHAR(1000), -- comma-separated sku_ids to exclude
  valid_from_date DATE,
  valid_to_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  CONSTRAINT fk_category FOREIGN KEY (category_id) REFERENCES dim_category(category_id)
);
```

**Example rows:**

| constraint_id | planogram_cluster_id | category_id | min_range_size | max_range_size | min_private_label_share |
|---------------|----------------------|-------------|-----------------|-----------------|------------------------|
| 4001 | 10 | 5 | 8 | 15 | 25 |
| 4002 | 20 | 5 | 10 | 18 | 30 |

---

### 10. `cfg_merchandising_rules`

**Purpose:** Advanced business rules (brand blocking, adjacency, etc.).

**Grain:** Per rule.

```sql
CREATE TABLE cfg_merchandising_rules (
  rule_id BIGINT PRIMARY KEY,
  rule_name VARCHAR(255) NOT NULL,
  rule_type VARCHAR(50), -- 'brand_blocking', 'adjacency', 'min_facings', 'segment_share', etc.
  scope_store_id BIGINT, -- NULL if all stores
  scope_cluster_id BIGINT,
  scope_category_id BIGINT NOT NULL,
  scope_brand_id BIGINT, -- NULL if rule applies to category level
  scope_segment VARCHAR(100), -- e.g., 'organic', 'value', etc.
  scope_sku_id BIGINT, -- NULL if applies to brand/segment
  parameter_1 VARCHAR(255), -- e.g., 'max_share' or 'mandatory' or 'adjacent_to_brand_id'
  parameter_1_value DECIMAL(10,2), -- e.g., 40.0 for 40% max
  parameter_2 VARCHAR(255),
  parameter_2_value DECIMAL(10,2),
  priority INT, -- lower = higher priority (for conflict resolution)
  is_active BOOLEAN DEFAULT TRUE,
  valid_from_date DATE,
  valid_to_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  CONSTRAINT fk_category FOREIGN KEY (scope_category_id) REFERENCES dim_category(category_id)
);
```

**Example rows:**

| rule_id | rule_name | rule_type | scope_category_id | scope_brand_id | parameter_1 | parameter_1_value |
|---------|-----------|-----------|-------------------|----------------|-------------|-------------------|
| 5001 | Max 40% Kelloggs | brand_blocking | 5 | 101 | max_share | 40.0 |
| 5002 | Min 20% Private Label | segment_share | 5 | NULL | min_share | 20.0 |
| 5003 | Top 3 SKUs Must Stock | min_facings | 5 | NULL | mandatory_skus | 1001,1005,1009 |

---

### 11. `cfg_sku_cost_margin`

**Purpose:** Cost and margin data (dynamic; can change with vendor negotiations, promos, etc.).

**Grain:** SKU × effective date range (slowly changing dimension, Type II).

```sql
CREATE TABLE cfg_sku_cost_margin (
  cost_margin_id BIGINT PRIMARY KEY,
  sku_id BIGINT NOT NULL,
  vendor_id BIGINT,
  cost_price DECIMAL(10,2),
  regular_retail_price DECIMAL(10,2),
  suggested_promo_price DECIMAL(10,2),
  gross_margin_pct DECIMAL(5,2), -- (retail - cost) / retail * 100
  contribution_margin DECIMAL(10,2),
  slotting_fee DECIMAL(10,2), -- one-time fee
  minimum_order_qty INT,
  order_multiple INT,
  lead_time_days INT,
  valid_from_date DATE NOT NULL,
  valid_to_date DATE, -- NULL if current
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (cost_margin_id),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES dim_sku(sku_id)
);
```

---

## Analytics & Derived Tables

### 12. `agg_sku_performance_weekly`

**Purpose:** Pre-aggregated SKU metrics for fast dashboard and model serving.

**Grain:** SKU × Week (rolled up from fact_sales_weekly).

```sql
CREATE TABLE agg_sku_performance_weekly (
  perf_id BIGINT PRIMARY KEY,
  sku_id BIGINT NOT NULL,
  week_start_date DATE NOT NULL,
  total_units_sold INT,
  total_sales_value DECIMAL(15,2),
  avg_price DECIMAL(10,2),
  promo_lift_pct DECIMAL(5,2), -- (promo vs baseline) / baseline
  stores_in_range_count INT,
  avg_availability_rate DECIMAL(5,2),
  segment_rank INT, -- rank within category
  created_at TIMESTAMP,
  PRIMARY KEY (perf_id),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES dim_sku(sku_id)
);

CREATE INDEX idx_perf_sku_week ON agg_sku_performance_weekly(sku_id, week_start_date);
```

---

### 13. `ml_demand_forecast`

**Purpose:** Output from demand modeling; feeds into optimizer.

**Grain:** Store (or Cluster) × SKU × Forecast period (e.g., weekly).

```sql
CREATE TABLE ml_demand_forecast (
  forecast_id BIGINT PRIMARY KEY,
  store_id BIGINT,
  planogram_cluster_id BIGINT,
  sku_id BIGINT NOT NULL,
  forecast_week_start_date DATE,
  baseline_demand_units INT, -- expected units without promotion
  demand_with_promo_units INT, -- expected with typical promotion
  demand_with_space_units INT, -- elasticity-adjusted demand
  forecast_accuracy_mape DECIMAL(5,2), -- mean absolute percentage error
  model_version VARCHAR(50),
  model_run_date DATE,
  created_at TIMESTAMP,
  PRIMARY KEY (forecast_id),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES dim_sku(sku_id)
);
```

---

### 14. `opt_recommended_planogram`

**Purpose:** Output from the HiGHS optimizer; recommended assortment and facings.

**Grain:** Store (or Cluster) × Category × SKU (after optimization run).

```sql
CREATE TABLE opt_recommended_planogram (
  opt_planogram_id BIGINT PRIMARY KEY,
  optimization_run_id BIGINT NOT NULL,
  store_id BIGINT,
  planogram_cluster_id BIGINT,
  category_id BIGINT NOT NULL,
  sku_id BIGINT NOT NULL,
  is_ranged_recommended BOOLEAN, -- 1 if in recommended range
  recommended_facings INT DEFAULT 0,
  recommended_shelf_level INT,
  recommended_position_order INT,
  expected_units_weekly INT,
  expected_sales_value_weekly DECIMAL(15,2),
  expected_margin_weekly DECIMAL(15,2),
  change_from_current VARCHAR(50), -- 'new', 'removed', 'increased', 'decreased', 'no_change'
  facings_change INT, -- new - old facings
  execution_difficulty VARCHAR(20), -- 'low', 'medium', 'high' (based on change magnitude)
  optimization_run_date DATE,
  valid_from_date DATE,
  created_at TIMESTAMP,
  PRIMARY KEY (opt_planogram_id),
  CONSTRAINT fk_store FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
  CONSTRAINT fk_category FOREIGN KEY (category_id) REFERENCES dim_category(category_id),
  CONSTRAINT fk_sku FOREIGN KEY (sku_id) REFERENCES dim_sku(sku_id)
);

CREATE INDEX idx_opt_store_cat ON opt_recommended_planogram(store_id, category_id);
CREATE INDEX idx_opt_run_date ON opt_recommended_planogram(optimization_run_date);
```

---

### 15. `opt_optimization_run_summary`

**Purpose:** Metadata about each optimization execution.

**Grain:** One row per optimization run.

```sql
CREATE TABLE opt_optimization_run_summary (
  optimization_run_id BIGINT PRIMARY KEY,
  run_name VARCHAR(255),
  scenario_type VARCHAR(50), -- 'current_state', 'space_expansion', 'range_rationalization', 'pl_growth'
  stores_included INT,
  categories_included INT,
  clusters_optimized INT,
  objective_value DECIMAL(20,2), -- Total expected profit, etc.
  total_expected_revenue DECIMAL(20,2),
  total_expected_margin DECIMAL(20,2),
  changes_sku_adds INT,
  changes_sku_removes INT,
  changes_sku_facings_changes INT,
  solver_name VARCHAR(50), -- 'HiGHS'
  solver_status VARCHAR(50), -- 'optimal', 'feasible', 'infeasible', etc.
  solver_time_seconds DECIMAL(10,2),
  model_version VARCHAR(50),
  run_timestamp TIMESTAMP NOT NULL,
  run_date DATE,
  created_by VARCHAR(100),
  created_at TIMESTAMP
);
```

---

### 16. `opt_constraint_violations` (Optional)

**Purpose:** Track constraint violations if solution is infeasible or near-infeasible.

**Grain:** Violation per optimization run.

```sql
CREATE TABLE opt_constraint_violations (
  violation_id BIGINT PRIMARY KEY,
  optimization_run_id BIGINT NOT NULL,
  store_id BIGINT,
  category_id BIGINT,
  constraint_type VARCHAR(100), -- 'shelf_space', 'min_range_size', 'brand_share', etc.
  constraint_name VARCHAR(255),
  violation_magnitude DECIMAL(15,2), -- e.g., 150 mm over capacity
  severity VARCHAR(20), -- 'warning', 'critical'
  created_at TIMESTAMP,
  CONSTRAINT fk_run FOREIGN KEY (optimization_run_id) REFERENCES opt_optimization_run_summary(optimization_run_id)
);
```

---

## Sample Data & Queries

### Sample Insert: Product Master

```sql
INSERT INTO dim_sku (sku_id, gtin_ean, sku_name, brand_id, manufacturer_id, category_id, 
                      pack_size, pack_size_uom, case_pack_qty, pack_width_mm, 
                      is_private_label, sku_status, created_at, updated_at)
VALUES
  (1001, 5012000456789, 'Crispy Flakes Cereal 500g', 101, 201, 51, 500, 'g', 20, 180, FALSE, 'active', NOW(), NOW()),
  (1002, 5012000456790, 'Value Cereal 750g', 102, 202, 5, 750, 'g', 15, 200, TRUE, 'active', NOW(), NOW()),
  (1003, 5012000456791, 'Organic Oats 400g', 103, 203, 52, 400, 'g', 24, 165, FALSE, 'active', NOW(), NOW()),
  (1004, 5012000456792, 'Kids Chocolate Cereal 300g', 104, 201, 51, 300, 'g', 30, 150, FALSE, 'active', NOW(), NOW()),
  (1005, 5012000456793, 'High Protein Granola 600g', 105, 204, 52, 600, 'g', 16, 190, FALSE, 'new', NOW(), NOW());
```

### Sample Query: SKU Performance Ranking (for model input)

```sql
SELECT 
  s.sku_id,
  s.sku_name,
  s.brand_id,
  s.category_id,
  SUM(f.units_sold) AS total_units_52w,
  SUM(f.net_sales_value) AS total_sales_52w,
  AVG(f.net_sales_value / NULLIF(f.units_sold, 0)) AS avg_price,
  COUNT(DISTINCT f.store_id) AS stores_in_range,
  ROUND(100.0 * SUM(CASE WHEN f.promo_flag THEN f.units_sold ELSE 0 END) / 
    NULLIF(SUM(f.units_sold), 0), 1) AS promo_driven_pct,
  ROUND(AVG(f.availability_rate), 1) AS avg_availability_pct
FROM dim_sku s
LEFT JOIN fact_sales_weekly f ON s.sku_id = f.sku_id
WHERE f.week_start_date >= CURRENT_DATE - INTERVAL 52 WEEK
GROUP BY s.sku_id, s.sku_name, s.brand_id, s.category_id
ORDER BY total_sales_52w DESC;
```

### Sample Query: Space Productivity Analysis

```sql
SELECT 
  c.category_name,
  s.brand_id,
  b.brand_name,
  SUM(p.total_facings * sk.pack_width_mm) AS total_facings_width_mm,
  SUM(f.units_sold) AS total_units,
  SUM(f.net_sales_value) AS total_sales,
  ROUND(SUM(f.net_sales_value) / NULLIF(SUM(p.total_facings), 0), 2) AS sales_per_facing,
  COUNT(DISTINCT p.store_id) AS stores
FROM fact_planogram_current p
JOIN dim_sku sk ON p.sku_id = sk.sku_id
JOIN dim_category c ON p.category_id = c.category_id
LEFT JOIN dim_brand b ON sk.brand_id = b.brand_id
LEFT JOIN fact_sales_weekly f ON p.sku_id = f.sku_id 
  AND p.store_id = f.store_id 
  AND f.week_start_date >= CURRENT_DATE - INTERVAL 4 WEEK
WHERE c.category_id = 5
GROUP BY c.category_name, sk.brand_id, b.brand_name
ORDER BY sales_per_facing DESC;
```

---

## Integration with HiGHS Optimization

### Pseudo-code: Building the MIP Model

```python
import pandas as pd
from highs import highs

# 1. Load data from tables
demand_df = pd.read_sql("""
  SELECT store_id, sku_id, baseline_demand_units 
  FROM ml_demand_forecast 
  WHERE forecast_week_start_date = ?
""", lakehouse_conn)

constraint_df = pd.read_sql("""
  SELECT * FROM cfg_range_constraints 
  WHERE category_id = ? AND valid_from_date <= CURRENT_DATE
""", lakehouse_conn)

cost_df = pd.read_sql("""
  SELECT * FROM cfg_sku_cost_margin 
  WHERE valid_to_date IS NULL
""", lakehouse_conn)

shelf_df = pd.read_sql("""
  SELECT * FROM fact_shelf_inventory
""", lakehouse_conn)

# 2. Define decision variables
# x[s, i] = 1 if SKU i is ranged in store s, 0 otherwise (binary)
# f[s, i] = facings for SKU i in store s (integer, >= 0)

# 3. Build objective: maximize sum of (profit_per_unit * demand * x[s,i])
objective_coefficients = {}
for (store, sku), row in demand_df.iterrows():
    profit = cost_df.loc[sku, 'contribution_margin']
    objective_coefficients[(store, sku)] = profit * row['baseline_demand_units']

# 4. Add constraints
# Constraint: Total width on shelf <= available width
# sum_i(facings[s, i] * pack_width[i]) <= shelf_width[s, c]

# Constraint: Link assortment to facings
# facings[s, i] <= M * x[s, i]  for all s, i

# Constraint: Min/Max range size
# L[c] <= sum_i(x[s, i]) <= U[c]  for all s, c

# ... etc.

# 5. Solve with HiGHS
model.optimize()

# 6. Extract solution
if model.solution_status == "optimal":
    results = extract_solution(model)
    # Write back to opt_recommended_planogram table
    write_optimization_results(results, optimization_run_id)
```

---

## Key Design Decisions

1. **Grain of fact_sales_weekly:** Store × SKU × Week
   - Allows flexible aggregation (by day, category, region)
   - Supports time-series demand modeling
   - Partitioning on week enables efficient queries

2. **Slow-Changing Dimensions (SCD Type II):**
   - `cfg_sku_cost_margin` includes `valid_from_date` and `valid_to_date`
   - Allows historical cost tracking and what-if scenarios

3. **Normalization:**
   - Separate dimension tables for brand, manufacturer, category
   - Enables efficient filtering and constraint generation

4. **Optimization Outputs Captured:**
   - `opt_recommended_planogram` stores full solver output
   - `opt_optimization_run_summary` tracks solver metadata
   - Enables auditing, sensitivity analysis, compliance tracking

5. **Cluster-Based Planning:**
   - Stores share `planogram_cluster_id`
   - Reduces optimization complexity; multiple stores reuse one planogram
   - Easy to override for store-specific needs

6. **Flexible Rule Engine:**
   - `cfg_merchandising_rules` is generic (rule_type, parameter_1/2)
   - Easy to add new rule types without schema changes
   - Priority field for conflict resolution

---

## Typical Data Volumes (Indicative)

For a retailer with ~300 stores, ~50 categories, ~20k SKUs:

- `dim_sku`: 20k rows
- `dim_store`: 300 rows
- `fact_sales_weekly`: ~52 weeks × 20k SKUs × 300 stores ÷ (clustering factor ~2) ≈ **150–300M rows** (Partitioned by week)
- `fact_planogram_current`: ~300 stores × 50 categories × avg 12 SKUs/cat ÷ clustering ≈ **90k rows**
- `cfg_*` tables: Typically <10k rows each
- `ml_demand_forecast`: Similar to fact_sales_weekly ≈ **150–300M rows**
- `opt_recommended_planogram`: Per optimization run; typically **100k–500k rows** depending on scope

---

## Extensions & Future Enhancements

1. **Competitor Pricing:** Add `fact_competitor_pricing` to model price-based demand elasticity
2. **Promotional Calendar:** Add `fact_promotional_events` to model promo uplift by event type
3. **In-Store Analytics:** Add `fact_store_traffic` and `fact_basket_analysis` for co-purchase rules
4. **Execution Tracking:** Add `fact_planogram_actual` to track real deployed layouts (vs recommended)
5. **Store-to-Store Dynamics:** Add cannibalization modeling for overlapping territories

---

This schema is production-ready and scalable for enterprise retail analytics and optimization workloads in a Lakehouse (Delta/Iceberg) environment.
