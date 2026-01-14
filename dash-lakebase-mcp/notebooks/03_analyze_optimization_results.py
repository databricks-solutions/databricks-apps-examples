# Databricks notebook source
# MAGIC %md
# MAGIC # 📊 Stock Optimization Analysis
# MAGIC 
# MAGIC This notebook explores and analyzes stock optimization results.
# MAGIC 
# MAGIC **Use the Data Science Assistant to:**
# MAGIC - Ask questions about the optimization results
# MAGIC - Generate visualizations
# MAGIC - Explore different scenarios
# MAGIC 
# MAGIC ## Try asking:
# MAGIC - "Which products have the highest profit margin?"
# MAGIC - "Create a bar chart of safety stock by product"
# MAGIC - "What's the correlation between demand variance and safety stock?"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Load the Model

# COMMAND ----------

# DBTITLE 1,Setup
import mlflow
import pandas as pd
import numpy as np

# Define widgets for job parameters (works when running interactively or as a job)
dbutils.widgets.text("catalog", "smarter_forecasting", "Catalog Name")
dbutils.widgets.text("schema", "stock_optimization", "Schema Name")

# Get parameter values
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
MODEL_NAME = "stock_optimizer"
UC_MODEL_PATH = f"{CATALOG}.{SCHEMA}.{MODEL_NAME}"

mlflow.set_registry_uri("databricks-uc")
print(f"📦 Loading model: {UC_MODEL_PATH}")

# COMMAND ----------

# DBTITLE 1,Load Model from Unity Catalog
try:
    model = mlflow.pyfunc.load_model(f"models:/{UC_MODEL_PATH}@production")
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Could not load from UC: {e}")
    print("Using local model instead...")
    # Fallback - you could also define the model inline here

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📋 Create Product Catalog
# MAGIC 
# MAGIC Realistic retail product data for analysis:

# COMMAND ----------

# DBTITLE 1,Generate Product Data
np.random.seed(42)

# Comprehensive product catalog
products = pd.DataFrame([
    # 🍺 Beer & Seltzer
    {'SELL_ID': 'BEV001', 'PRODUCT_NAME': 'Stone & Wood Pacific Ale 6pk', 'CATEGORY': 'Beer', 'AVG_DAILY_DEMAND': 180, 'DEMAND_STD': 63, 'UNIT_COST': 14, 'SELLING_PRICE': 24},
    {'SELL_ID': 'BEV002', 'PRODUCT_NAME': 'Balter XPA 4pk', 'CATEGORY': 'Beer', 'AVG_DAILY_DEMAND': 150, 'DEMAND_STD': 45, 'UNIT_COST': 12, 'SELLING_PRICE': 20},
    {'SELL_ID': 'BEV003', 'PRODUCT_NAME': 'Young Henrys Newtowner 6pk', 'CATEGORY': 'Beer', 'AVG_DAILY_DEMAND': 165, 'DEMAND_STD': 53, 'UNIT_COST': 13, 'SELLING_PRICE': 22},
    {'SELL_ID': 'BEV004', 'PRODUCT_NAME': 'White Claw Variety 12pk', 'CATEGORY': 'Seltzer', 'AVG_DAILY_DEMAND': 200, 'DEMAND_STD': 50, 'UNIT_COST': 18, 'SELLING_PRICE': 32},
    {'SELL_ID': 'BEV005', 'PRODUCT_NAME': 'Fellr Watermelon 4pk', 'CATEGORY': 'Seltzer', 'AVG_DAILY_DEMAND': 120, 'DEMAND_STD': 34, 'UNIT_COST': 11, 'SELLING_PRICE': 18},
    {'SELL_ID': 'BEV006', 'PRODUCT_NAME': 'Corona Extra 6pk', 'CATEGORY': 'Beer', 'AVG_DAILY_DEMAND': 220, 'DEMAND_STD': 44, 'UNIT_COST': 12, 'SELLING_PRICE': 20},
    
    # 🌶️ Hot Sauce
    {'SELL_ID': 'SAU001', 'PRODUCT_NAME': 'Sriracha Original 455ml', 'CATEGORY': 'Hot Sauce', 'AVG_DAILY_DEMAND': 45, 'DEMAND_STD': 9, 'UNIT_COST': 6, 'SELLING_PRICE': 12},
    {'SELL_ID': 'SAU002', 'PRODUCT_NAME': 'Tabasco Original 150ml', 'CATEGORY': 'Hot Sauce', 'AVG_DAILY_DEMAND': 35, 'DEMAND_STD': 5, 'UNIT_COST': 4, 'SELLING_PRICE': 8},
    {'SELL_ID': 'SAU003', 'PRODUCT_NAME': 'Cholula Original 150ml', 'CATEGORY': 'Hot Sauce', 'AVG_DAILY_DEMAND': 40, 'DEMAND_STD': 8, 'UNIT_COST': 5, 'SELLING_PRICE': 10},
    {'SELL_ID': 'SAU004', 'PRODUCT_NAME': 'Da Bomb Beyond Insanity 118ml', 'CATEGORY': 'Hot Sauce', 'AVG_DAILY_DEMAND': 8, 'DEMAND_STD': 4, 'UNIT_COST': 12, 'SELLING_PRICE': 25},
    {'SELL_ID': 'SAU005', 'PRODUCT_NAME': 'Bunsters Black Label 236ml', 'CATEGORY': 'Hot Sauce', 'AVG_DAILY_DEMAND': 15, 'DEMAND_STD': 6, 'UNIT_COST': 10, 'SELLING_PRICE': 20},
    
    # 🍦 Ice Cream
    {'SELL_ID': 'ICE001', 'PRODUCT_NAME': "Ben & Jerry's Cookie Dough 458ml", 'CATEGORY': 'Ice Cream', 'AVG_DAILY_DEMAND': 85, 'DEMAND_STD': 26, 'UNIT_COST': 9, 'SELLING_PRICE': 14},
    {'SELL_ID': 'ICE002', 'PRODUCT_NAME': 'Häagen-Dazs Salted Caramel 457ml', 'CATEGORY': 'Ice Cream', 'AVG_DAILY_DEMAND': 70, 'DEMAND_STD': 20, 'UNIT_COST': 10, 'SELLING_PRICE': 15},
    {'SELL_ID': 'ICE003', 'PRODUCT_NAME': 'Connoisseur Murray River Caramel 1L', 'CATEGORY': 'Ice Cream', 'AVG_DAILY_DEMAND': 55, 'DEMAND_STD': 14, 'UNIT_COST': 8, 'SELLING_PRICE': 13},
    {'SELL_ID': 'ICE004', 'PRODUCT_NAME': 'Halo Top Birthday Cake 473ml', 'CATEGORY': 'Ice Cream', 'AVG_DAILY_DEMAND': 45, 'DEMAND_STD': 16, 'UNIT_COST': 7, 'SELLING_PRICE': 12},
    {'SELL_ID': 'ICE005', 'PRODUCT_NAME': 'Magnum Double Caramel 4pk', 'CATEGORY': 'Ice Cream', 'AVG_DAILY_DEMAND': 60, 'DEMAND_STD': 13, 'UNIT_COST': 8, 'SELLING_PRICE': 13},
])

# Convert to float for model
products['AVG_DAILY_DEMAND'] = products['AVG_DAILY_DEMAND'].astype(float)
products['DEMAND_STD'] = products['DEMAND_STD'].astype(float)
products['UNIT_COST'] = products['UNIT_COST'].astype(float)
products['SELLING_PRICE'] = products['SELLING_PRICE'].astype(float)

print(f"📦 {len(products)} products loaded")
display(products)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎯 Run Optimization

# COMMAND ----------

# DBTITLE 1,Optimize All Products
# Prepare input (model expects specific columns)
model_input = products[['SELL_ID', 'PRODUCT_NAME', 'AVG_DAILY_DEMAND', 'DEMAND_STD', 'UNIT_COST', 'SELLING_PRICE']].copy()

# Run optimization
results = model.predict(model_input)

# Add category back for analysis
results['CATEGORY'] = products['CATEGORY'].values

print(f"✅ Optimized {len(results)} products")
display(results)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📈 Analysis & Visualization
# MAGIC 
# MAGIC **💡 Tip: Use the Data Science Assistant to ask questions!**

# COMMAND ----------

# DBTITLE 1,Summary Statistics
print("="*60)
print("📊 OPTIMIZATION SUMMARY")
print("="*60)

print(f"\n💰 Financial Overview:")
print(f"   Total Annual Revenue:  ${results['EXPECTED_ANNUAL_REVENUE'].sum():>14,.2f}")
print(f"   Total Annual Cost:     ${results['TOTAL_ANNUAL_COST'].sum():>14,.2f}")
print(f"   Total Annual Profit:   ${results['EXPECTED_ANNUAL_PROFIT'].sum():>14,.2f}")

print(f"\n📦 Inventory Overview:")
print(f"   Total Optimal Stock:   {results['OPTIMAL_ORDER_QTY'].sum():>14,.0f} units")
print(f"   Total Safety Stock:    {results['SAFETY_STOCK'].sum():>14,.0f} units")
print(f"   Total Max Stock:       {results['MAX_STOCK_LEVEL'].sum():>14,.0f} units")

print(f"\n📈 Performance Metrics:")
print(f"   Avg Turnover Rate:     {results['TURNOVER_RATE'].mean():>14.1f}x")
print(f"   Service Level:         {results['SERVICE_LEVEL'].iloc[0]*100:>13.0f}%")

# COMMAND ----------

# DBTITLE 1,Results by Category
category_summary = results.groupby('CATEGORY').agg({
    'SELL_ID': 'count',
    'OPTIMAL_ORDER_QTY': 'sum',
    'SAFETY_STOCK': 'sum',
    'TOTAL_ANNUAL_COST': 'sum',
    'EXPECTED_ANNUAL_PROFIT': 'sum',
    'TURNOVER_RATE': 'mean',
}).rename(columns={'SELL_ID': 'Products'})

print("📁 Results by Category:")
display(category_summary)

# COMMAND ----------

# DBTITLE 1,Top Products by Profit
top_profit = results.nlargest(10, 'EXPECTED_ANNUAL_PROFIT')[
    ['PRODUCT_NAME', 'CATEGORY', 'AVG_DAILY_DEMAND', 'OPTIMAL_ORDER_QTY', 'EXPECTED_ANNUAL_PROFIT']
]
print("🏆 Top 10 Products by Expected Profit:")
display(top_profit)

# COMMAND ----------

# DBTITLE 1,Products Requiring Most Safety Stock
high_safety = results.nlargest(10, 'SAFETY_STOCK')[
    ['PRODUCT_NAME', 'CATEGORY', 'AVG_DAILY_DEMAND', 'SAFETY_STOCK', 'REORDER_POINT']
]
print("⚠️ Products Requiring Most Safety Stock:")
display(high_safety)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Visualizations

# COMMAND ----------

# DBTITLE 1,Profit by Category (Pie Chart)
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))
category_profit = results.groupby('CATEGORY')['EXPECTED_ANNUAL_PROFIT'].sum()
ax.pie(category_profit, labels=category_profit.index, autopct='%1.1f%%', startangle=90)
ax.set_title('Expected Annual Profit by Category')
plt.tight_layout()
display(fig)

# COMMAND ----------

# DBTITLE 1,Optimal Stock vs Safety Stock
fig, ax = plt.subplots(figsize=(12, 6))
x = range(len(results))
width = 0.35

ax.bar([i - width/2 for i in x], results['OPTIMAL_ORDER_QTY'], width, label='Optimal Order Qty', color='steelblue')
ax.bar([i + width/2 for i in x], results['SAFETY_STOCK'], width, label='Safety Stock', color='coral')

ax.set_xlabel('Product')
ax.set_ylabel('Units')
ax.set_title('Optimal Order Quantity vs Safety Stock by Product')
ax.set_xticks(x)
ax.set_xticklabels([p[:15] + '...' if len(p) > 15 else p for p in results['PRODUCT_NAME']], rotation=45, ha='right')
ax.legend()
plt.tight_layout()
display(fig)

# COMMAND ----------

# DBTITLE 1,Demand vs Turnover Rate
fig, ax = plt.subplots(figsize=(10, 6))
colors = {'Beer': 'gold', 'Seltzer': 'lightblue', 'Hot Sauce': 'red', 'Ice Cream': 'pink'}
for cat in results['CATEGORY'].unique():
    cat_data = results[results['CATEGORY'] == cat]
    ax.scatter(cat_data['AVG_DAILY_DEMAND'], cat_data['TURNOVER_RATE'], 
               label=cat, c=colors.get(cat, 'gray'), s=100, alpha=0.7)

ax.set_xlabel('Average Daily Demand')
ax.set_ylabel('Turnover Rate (x per year)')
ax.set_title('Demand vs Turnover Rate by Category')
ax.legend()
plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Scenario Analysis
# MAGIC 
# MAGIC Try different scenarios by adjusting parameters:

# COMMAND ----------

# DBTITLE 1,What-If: High Demand Season
# Simulate 50% demand increase
high_demand = model_input.copy()
high_demand['AVG_DAILY_DEMAND'] = high_demand['AVG_DAILY_DEMAND'] * 1.5
high_demand['DEMAND_STD'] = high_demand['DEMAND_STD'] * 1.5

high_results = model.predict(high_demand)

print("📈 HIGH DEMAND SCENARIO (+50% demand)")
print(f"   Additional Stock Needed: {(high_results['OPTIMAL_ORDER_QTY'].sum() - results['OPTIMAL_ORDER_QTY'].sum()):,.0f} units")
print(f"   Additional Safety Stock: {(high_results['SAFETY_STOCK'].sum() - results['SAFETY_STOCK'].sum()):,.0f} units")
print(f"   Profit Increase: ${(high_results['EXPECTED_ANNUAL_PROFIT'].sum() - results['EXPECTED_ANNUAL_PROFIT'].sum()):,.2f}")

# COMMAND ----------

# DBTITLE 1,What-If: Low Demand Season
# Simulate 30% demand decrease
low_demand = model_input.copy()
low_demand['AVG_DAILY_DEMAND'] = low_demand['AVG_DAILY_DEMAND'] * 0.7
low_demand['DEMAND_STD'] = low_demand['DEMAND_STD'] * 0.7

low_results = model.predict(low_demand)

print("📉 LOW DEMAND SCENARIO (-30% demand)")
print(f"   Stock Reduction: {(results['OPTIMAL_ORDER_QTY'].sum() - low_results['OPTIMAL_ORDER_QTY'].sum()):,.0f} units")
print(f"   Safety Stock Reduction: {(results['SAFETY_STOCK'].sum() - low_results['SAFETY_STOCK'].sum()):,.0f} units")
print(f"   Profit Change: ${(low_results['EXPECTED_ANNUAL_PROFIT'].sum() - results['EXPECTED_ANNUAL_PROFIT'].sum()):,.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 💡 Data Science Assistant Tips
# MAGIC 
# MAGIC Try asking:
# MAGIC - "Show me the relationship between unit cost and profit margin"
# MAGIC - "Which category has the most volatile demand?"
# MAGIC - "Create a heatmap of the correlation between all numeric columns"
# MAGIC - "What would happen if we increased the safety factor to 2.0?"
# MAGIC - "Plot the cumulative profit curve sorted by profit"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📤 Export Results

# COMMAND ----------

# DBTITLE 1,Save to Delta Table
# Save results to Delta table for future analysis
results_table = f"{CATALOG}.{SCHEMA}.optimization_results"

spark_df = spark.createDataFrame(results)
spark_df.write.mode("overwrite").saveAsTable(results_table)

print(f"✅ Results saved to: {results_table}")
