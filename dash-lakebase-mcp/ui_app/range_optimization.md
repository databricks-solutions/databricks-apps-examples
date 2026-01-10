Range Optimizer: Typical Datasets, Analytics, and HiGHS Usage
Main idea: A supermarket “range optimizer” is essentially an assortment + space optimization engine. It sits on top of a set of well-structured retail datasets (product, store, sales, shelf/space, costs, and rules), transforms them into demand/space productivity signals, and then formulates a mixed-integer optimization problem that a solver like HiGHS can solve to recommend the optimal range and shelf layout.

Below is a structured view of:

The typical datasets (with suggested schemas)

The analytics performed before and after optimization

How those feed into a HiGHS-based optimization model

1. Core Concept of the Range Optimizer
At a high level, the application decides, for each store × category:

Which SKUs to carry (assortment)

How much space / how many facings each SKU gets (space allocation)

Optionally, exactly where each SKU goes on the shelf (planogram positions)

Subject to:

Physical shelf constraints (width/height/depth, capacity)

Commercial rules (must-stock items, private-label targets, brand blocking)

Operational rules (minimum facings, safety stock, case-pack constraints)

Financial objectives (maximize profit, revenue, or some weighted utility)

HiGHS is then used to solve the resulting linear / mixed-integer model.

2. Typical Datasets (Schemas and Roles)
Below are the main datasets you would expect to have in a range optimizer. Think of these as logical tables in your lakehouse.

2.1 Product Master (SKU-level)
Grain: One row per SKU.

Key purpose: Identify attributes that drive demand, substitution, and merchandising rules.

Key fields:

sku_id (PK)

gtin_ean_upc

sku_name

brand_name

manufacturer_name

category_id

segment (e.g., “Kids Cereals”, “Adult Health”, “Value”)

subsegment

pack_size (e.g., “500g”, “1L”)

pack_type (box, bottle, pouch, etc.)

uom (g, ml, etc.)

case_pack_size (units per case)

shelf_life_days

status (active, discontinued, new)

launch_date, discontinue_date

These attributes are used for:

Similarity and substitution (within a category)

Business rules (e.g., “always carry at least 1 sugar-free variant”)

Space layout (e.g., bottle vs box may need different shelf heights)

2.2 Store Master
Grain: One row per store.

Key purpose: Store characteristics for clustering and constraints.

Key fields:

store_id (PK)

store_name

store_format (hypermarket, supermarket, convenience, etc.)

store_size_sqm

region, city, postcode

affluence_segment (e.g., low/medium/high based on area)

demographic_profile (high-level; e.g., “families”, “students”)

opening_date, closing_date (if applicable)

These drive:

Store clustering (similar stores share planograms)

Range differentiation by format or region

Category roles differing by store type

2.3 Category Hierarchy
Grain: One row per category (and subcategory if used).

Key purpose: Category roles and strategies.

Key fields:

category_id (PK)

category_name (e.g., “Breakfast Cereals”)

department (e.g., Grocery, Fresh, Non-Food)

category_role (destination, routine, convenience, seasonal, etc.)

space_priority (categorical or rank)

min_range_size, max_range_size (number of SKUs)

default_planogram_type (if you use templates)

These parameters influence the optimization objective and constraints. Destination categories may be allowed more space or a larger range.

2.4 Historical Sales & Demand
Grain: Typically store × sku × time (e.g., week).

Key purpose: Estimate baseline demand, seasonality, and performance metrics.

Key fields:

store_id

sku_id

week_start_date (or other time period)

units_sold

net_sales_value

regular_price

promo_flag

promo_type

on_display_flag (endcap, secondary placement)

out_of_stock_flag or availability_rate

This dataset is the primary input to:

Demand modeling (baseline vs promotional uplift)

Space elasticity estimation (if you have historical space changes)

SKU performance ranking (velocity, value, margin contribution)

2.5 Cost, Margin and Vendor Terms
Grain: SKU-level (sometimes store × sku if costs vary).

Key purpose: Financial inputs to the objective function.

Key fields:

sku_id

cost_price

regular_retail_price (baseline)

gross_margin_per_unit (or derived)

vendor_id

pay_for_space_flag or slotting_fee

promo_funding_terms

rebate_scheme parameters

These feed into per-SKU profit coefficients in the optimization model.

2.6 Shelf / Planogram Structure
Grain: Store × category × shelf segment, or a generic template.

Key purpose: Physical constraints for placement and space.

Key fields:

store_id (or cluster_id if using a common planogram)

category_id

shelf_id (e.g., “Gondola 3, side A”)

shelf_level (shelf 1–5 from bottom)

shelf_width_mm

shelf_depth_mm

shelf_height_mm

max_weight_kg

is_chilled_flag (for chilled/frozen fixtures)

This is where total available space constraints come from.

2.7 Planogram Position / Facing Data (Current vs Recommended)
Grain: Store × category × sku × position.

For the current planogram:

store_id

category_id

sku_id

shelf_id

shelf_level

start_position_mm (from shelf left)

facings_horizontal

facings_vertical

depth_positions (number of items deep)

effective_space_width_mm (derivable from facings × pack width)

For recommended planograms, the optimizer will generate similar fields as output.

2.8 Packaging Dimensions
Grain: SKU-level.

Key purpose: Convert facings to physical space.

Key fields:

sku_id

pack_width_mm

pack_depth_mm

pack_height_mm

orientation_constraints (must be upright, can be laid flat, etc.)

These are essential for constraints such as:

Total width used on a shelf ≤ shelf width

Total height ≤ shelf height

Case-pack fit vs shelf depth

2.9 Operational & Merchandising Rules
Grain: Depends; could be per category, per brand, or per sku.

Key purpose: Model non-physical business constraints.

Examples of fields:

rule_id

rule_type (must-stock, cannot-stock, min-facings, adjacency, blocking)

scope_level (category, brand, sku, segment)

store_scope (e.g., all stores, only specific region/format)

parameter_1, parameter_2 (e.g., min facings, max items per brand)

Typical rule types:

Must-carry SKUs: “Top 10 SKUs by sales in category X must be listed in all stores of format Y.”

Min/max facings: “Private label cereal must have at least 3 facings on eye-level shelves.”

Range breadth: “At least 3 gluten-free options if category role is destination.”

Brand blocking: “No more than 60% of facings from a single manufacturer on any one shelf.”

These get translated into linear constraints.

2.10 Inventory and Supply Constraints (Optional but Valuable)
Grain: Store × sku or distribution center × sku.

Key purpose: Ensure the optimized range is executable given supply.

Key fields:

store_id / dc_id

sku_id

lead_time_days

min_order_qty

order_multiple

service_level_target

These can influence stock constraints or penalties for low-service SKUs.

3. Pre-Optimization Analytics
Before using HiGHS, the data is transformed into model-ready inputs. Typical analytics:

3.1 Demand Modeling per SKU and Store (or Cluster)
Goal: Estimate baseline demand and sensitivity to factors like price, promotion, and space.

Typical steps:

Clean sales data (handle out-of-stocks, abnormal promos).

De-seasonalize and de-trend time series.

Fit models (e.g., regression, gradient boosting, or MLE-based models) to estimate:

Baseline demand 
d
s
,
i
d 
s,i
  per store 
s
s, SKU 
i
i.

Price elasticity, promo lift factors.

Optionally model space elasticity if historical changes in space exist.

The core number the optimizer needs is something like:

expected_weekly_units per store × sku under current or target conditions.

3.2 Store Clustering
Goal: Reduce complexity by grouping similar stores and sharing planograms.

Typical features:

Sales mix by category and key segments

Store size, format, region

Demographics and income level

Output:

store_id, planogram_cluster_id

Then the optimization may run at cluster × category level, rather than per-store.

3.3 SKU Performance Scoring
Goal: Understand which SKUs are “core” vs “tail”.

Typical metrics:

Velocity: units per week

Value: sales value per week

Margin: profit per facings unit of space

LOS / OOS frequency (stock issues)

Promo reliance ratio (what % of sales from promotions)

Output fields:

sku_id

performance_score (composite index)

core_range_flag, tail_flag, new_flag

These feed business rules (e.g., always keep core SKUs, tail SKUs are more flexible).

3.4 Space Productivity Metrics
Goal: Quantify sales or profit per unit of space.

Using planogram and sales data:

Compute for each store × sku:

space_width_mm = facings × pack width

sales_per_mm or profit_per_mm

Aggregate to:

sales_per_shelf_mm per shelf segment

profit_per_shelf_mm per shelf segment

These help:

Identify underperforming brands/segments hogging space

Set intuitive constraints (e.g., don’t reduce highly productive blocks too much)

3.5 Constraint Parameterization
Goal: Turn business logic into numerical parameters.

Examples:

For each category:

min_range_size, max_range_size (number of SKUs)

For each SKU / brand:

min_facings, max_facings

must_stock_flag

For each store/cluster × category:

total_shelf_width_mm available

For each segment:

min_share_of_range or min_share_of_facings

These become explicit parameters in the optimization model.

4. Optimization Model and HiGHS Usage
HiGHS is a high-performance solver for linear programming (LP) and mixed-integer programming (MIP). Range optimization usually requires MIP.

4.1 Typical Decision Variables
Examples of variable definitions:

Assortment decision:

x
s
,
i
∈
{
0
,
1
}
x 
s,i
 ∈{0,1}: 1 if SKU 
i
i is ranged in store (or cluster) 
s
s.

Facings / space:

f
s
,
i
≥
0
f 
s,i
 ≥0: number of facings for SKU 
i
i in store 
s
s (integer or continuous, often integer).

Shelf placement (if modeling exact positions):

y
s
,
i
,
p
∈
{
0
,
1
}
y 
s,i,p
 ∈{0,1}: 1 if SKU 
i
i occupies position 
p
p (a slot on a given shelf) in store 
s
s.

Depending on implementation, you may:

Treat f_{s,i} as integers and derive shelf usage from dimensions.

Or discretize shelf space into slots and use binary variables per slot.

4.2 Objective Function
Common objective: maximize total profit (or contribution), sometimes with penalties for rule violations or changes.

Example (simplified):

max
⁡
∑
s
∑
i
π
s
,
i
⋅
q
s
,
i
(
f
s
,
i
)
⋅
x
s
,
i
max 
s
∑
  
i
∑
 π 
s,i
 ⋅q 
s,i
 (f 
s,i
 )⋅x 
s,i
 
Where:

π
s
,
i
π 
s,i
 : profit per unit for SKU 
i
i in store 
s
s.

q
s
,
i
(
f
s
,
i
)
q 
s,i
 (f 
s,i
 ): expected demand as a function of facings 
f
s
,
i
f 
s,i
 .

In practice, to keep it linear, one often uses:

A fixed expected demand 
d
s
,
i
d 
s,i
  and optionally piecewise linear approximations for space effects; or

Linearized elasticity models where demand increases linearly with facings within bounds.

Alternatively, the objective can be:

A multi-objective mix: profit + range breadth + private label share (using weights).

4.3 Key Constraints
Examples of linear constraints:

Shelf space capacity:

For each store (or cluster) 
s
s and category 
c
c:

∑
i
∈
c
f
s
,
i
⋅
w
i
≤
W
s
,
c
i∈c
∑
 f 
s,i
 ⋅w 
i
 ≤W 
s,c
 
w
i
w 
i
 : pack width of SKU 
i
i

W
s
,
c
W 
s,c
 : total shelf width for category 
c
c in store 
s
s

Link assortment and facings:

f
s
,
i
≤
M
⋅
x
s
,
i
f 
s,i
 ≤M⋅x 
s,i
 
If SKU is not ranged (
x
s
,
i
=
0
x 
s,i
 =0), then 
f
s
,
i
=
0
f 
s,i
 =0.

M
M: a large upper bound on facings.

Min/max range size (breadth):

L
s
,
c
≤
∑
i
∈
c
x
s
,
i
≤
U
s
,
c
L 
s,c
 ≤ 
i∈c
∑
 x 
s,i
 ≤U 
s,c
 
Where 
L
s
,
c
L 
s,c
 , 
U
s
,
c
U 
s,c
  are min/max number of SKUs in category 
c
c.

Must-stock SKUs:

For required SKUs 
i
∈
R
s
,
c
i∈R 
s,c
 :

x
s
,
i
=
1
x 
s,i
 =1
Minimum facings for listed SKUs:

f
s
,
i
≥
f
i
min
⁡
⋅
x
s
,
i
f 
s,i
 ≥f 
i
min
 ⋅x 
s,i
 
Brand or segment share constraints:

For a brand 
b
b in category 
c
c:

∑
i
∈
b
f
s
,
i
≤
α
b
,
c
⋅
∑
j
∈
c
f
s
,
j
i∈b
∑
 f 
s,i
 ≤α 
b,c
 ⋅ 
j∈c
∑
 f 
s,j
 
Where 
α
b
,
c
α 
b,c
  is a max share.

Private label target:

∑
i
∈
PL
f
s
,
i
≥
β
c
⋅
∑
j
∈
c
f
s
,
j
i∈PL
∑
 f 
s,i
 ≥β 
c
 ⋅ 
j∈c
∑
 f 
s,j
 
Where 
β
c
β 
c
  is a minimum private label share.

Adjacency / blocking (if modeled):

These can be encoded using additional binary variables and big-M constraints (e.g., forcing contiguous block of facings for a brand or segment).

All of this is expressed as a MIP and then given to HiGHS through its APIs (C++, Python, or via an intermediate modeling layer). HiGHS returns the optimal values for 
x
s
,
i
x 
s,i
 , 
f
s
,
i
f 
s,i
 , and optionally 
y
s
,
i
,
p
y 
s,i,p
 .

5. Post-Optimization Analyses
Once HiGHS returns an optimal solution, several analyses are typical.

5.1 Range Changes and Impact
Per store (or cluster) × category:

Add / Drop list:

SKUs where 
x
s
,
i
new
=
1
x 
s,i
new
 =1 and 
x
s
,
i
old
=
0
x 
s,i
old
 =0.

SKUs where 
x
s
,
i
new
=
0
x 
s,i
new
 =0 and 
x
s
,
i
old
=
1
x 
s,i
old
 =1.

Impact metrics:

Change in expected units and value.

Change in margin.

Change in facings per SKU.

This powers merchandising dashboards and execution lists.

5.2 Space Reallocation Analysis
Per shelf or category:

Facings by brand, segment, and private label before vs after.

Sales/profit per mm of shelf before vs after.

Identification of winners (brands/segments gaining space) and losers.

5.3 Financial Scenario Analysis
Run the model under different assumptions:

Increased/decreased total shelf space (e.g., remodeling).

More aggressive private label constraints.

Adjusted demand assumptions (optimistic/pessimistic scenarios).

Tighter or looser range size constraints.

Compare:

Total profit across scenarios.

Number of range changes required.

Execution complexity (e.g., number of SKUs that change location).

5.4 Sensitivity and “What-If” Analyses
Examples:

New SKU introduction: Add candidate SKUs with estimated demand and costs, re-run optimization to see which make it into the range.

Discontinuations: Force certain SKUs to be dropped and analyze re-allocated demand and space.

Assortment rationalization: Force tighter max range size and see impact on profit.

HiGHS can also provide dual values / reduced costs for LP parts of the problem, which can be used to interpret:

Shadow prices of shelf space (the marginal value of an extra mm).

The opportunity cost of including low-performing SKUs.

5.5 Execution and Compliance Analytics
Once the recommended planograms are deployed:

Monitor actual sales vs expected.

Track compliance: difference between recommended and observed planograms (from store audits or image recognition).

Re-estimate demand and space elasticity periodically and update models.

6. How to Think About the “Typical Dataset” Deliverables
For actual implementation (e.g., in a Lakehouse), you would likely define:

Dim tables:

dim_sku

dim_store

dim_category

dim_vendor

Fact tables:

fact_sales_weekly (store × sku × week)

fact_planogram_current (store × category × sku × shelf segment)

fact_space_measures (derived facings and mm)

fact_optimization_results (new assortment, facings, positions)

fact_demand_estimates (expected units/profit per store × sku)

Rule/config tables:

cfg_category_role

cfg_range_constraints

cfg_merchandising_rules

cfg_price_cost

These datasets are the backbone that the optimizer and HiGHS consume and that analytics/reporting layers query.

