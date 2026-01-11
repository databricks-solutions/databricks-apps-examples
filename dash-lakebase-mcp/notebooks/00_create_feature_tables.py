# Databricks notebook source
# MAGIC %md
# MAGIC # 🎯 Create Feature Tables for Stock Optimization
# MAGIC 
# MAGIC This notebook creates **Feature Tables** in Unity Catalog that will be used for training and inference.
# MAGIC 
# MAGIC ## What You'll Learn
# MAGIC - Create feature tables in Unity Catalog
# MAGIC - Define feature schemas for product demand forecasting
# MAGIC - Populate feature tables with realistic retail data
# MAGIC - Use Feature Engineering client for Unity Catalog

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📝 Configuration

# COMMAND ----------

# DBTITLE 1,Configuration
CATALOG = "main"                           # Your Unity Catalog name
SCHEMA = "stock_optimization"              # Schema for features and models
PRODUCT_FEATURES_TABLE = "product_features"
DEMAND_FEATURES_TABLE = "demand_features"

# Full UC paths
PRODUCT_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{PRODUCT_FEATURES_TABLE}"
DEMAND_FEATURES_PATH = f"{CATALOG}.{SCHEMA}.{DEMAND_FEATURES_TABLE}"

print(f"📦 Product Features Table: {PRODUCT_FEATURES_PATH}")
print(f"📊 Demand Features Table: {DEMAND_FEATURES_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📚 Install Dependencies

# COMMAND ----------

# MAGIC %pip install databricks-feature-engineering -q
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔧 Setup

# COMMAND ----------

# DBTITLE 1,Import Libraries
import pandas as pd
import numpy as np
from pyspark.sql import DataFrame
from pyspark.sql.types import *
from databricks.feature_engineering import FeatureEngineeringClient
from datetime import datetime, timedelta

# Initialize Feature Engineering Client
fe = FeatureEngineeringClient()
print("✅ Feature Engineering Client initialized")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🗄️ Create Unity Catalog Schema

# COMMAND ----------

# DBTITLE 1,Setup Catalog & Schema
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"✅ Created {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📦 Feature Table 1: Product Features
# MAGIC 
# MAGIC This table contains **static product attributes** that influence demand and optimization:
# MAGIC - Product identifiers and names
# MAGIC - Unit costs and selling prices  
# MAGIC - Category information
# MAGIC - Shelf space allocation

# COMMAND ----------

# DBTITLE 1,Generate Product Features Data
def generate_product_features():
    """Generate realistic product feature data"""
    np.random.seed(42)
    
    # Product catalog across three categories
    products = [
        # Beer & Seltzer (5 products)
        {'name': 'Stone & Wood Pacific Ale 6pk', 'category': 'Beer & Seltzer', 'subcategory': 'Craft Beer', 'shelf_cm': 45, 'cost': 14},
        {'name': 'Balter XPA 4pk', 'category': 'Beer & Seltzer', 'subcategory': 'Craft Beer', 'shelf_cm': 35, 'cost': 12},
        {'name': 'Young Henrys Newtowner 6pk', 'category': 'Beer & Seltzer', 'subcategory': 'Craft Beer', 'shelf_cm': 40, 'cost': 13},
        {'name': 'White Claw Variety 12pk', 'category': 'Beer & Seltzer', 'subcategory': 'Hard Seltzer', 'shelf_cm': 50, 'cost': 18},
        {'name': 'Fellr Watermelon 4pk', 'category': 'Beer & Seltzer', 'subcategory': 'Hard Seltzer', 'shelf_cm': 30, 'cost': 11},
        
        # Hot Sauce (5 products)
        {'name': 'Sriracha Original 455ml', 'category': 'Hot Sauce', 'subcategory': 'Asian Style', 'shelf_cm': 18, 'cost': 6},
        {'name': 'Tabasco Original 150ml', 'category': 'Hot Sauce', 'subcategory': 'Louisiana Style', 'shelf_cm': 15, 'cost': 4},
        {'name': 'Cholula Original 150ml', 'category': 'Hot Sauce', 'subcategory': 'Mexican Style', 'shelf_cm': 16, 'cost': 5},
        {'name': 'Da Bomb Beyond Insanity 118ml', 'category': 'Hot Sauce', 'subcategory': 'Extreme Heat', 'shelf_cm': 8, 'cost': 12},
        {'name': 'Bunsters Black Label 236ml', 'category': 'Hot Sauce', 'subcategory': 'Craft/Artisan', 'shelf_cm': 12, 'cost': 10},
        
        # Ice Cream (5 products)
        {'name': "Ben & Jerry's Cookie Dough 458ml", 'category': 'Ice Cream', 'subcategory': 'Premium Pints', 'shelf_cm': 17, 'cost': 9},
        {'name': 'Häagen-Dazs Salted Caramel 457ml', 'category': 'Ice Cream', 'subcategory': 'Premium Pints', 'shelf_cm': 17, 'cost': 10},
        {'name': 'Connoisseur Murray River Caramel 1L', 'category': 'Ice Cream', 'subcategory': 'Premium Tubs', 'shelf_cm': 22, 'cost': 8},
        {'name': 'Halo Top Birthday Cake 473ml', 'category': 'Ice Cream', 'subcategory': 'Low-Cal Pints', 'shelf_cm': 15, 'cost': 7},
        {'name': 'Magnum Double Caramel 4pk', 'category': 'Ice Cream', 'subcategory': 'Sticks/Bars', 'shelf_cm': 20, 'cost': 8},
    ]
    
    data = []
    for i, p in enumerate(products):
        # Add some realistic variability to costs
        unit_cost = p['cost'] * np.random.uniform(0.95, 1.05)
        selling_price = unit_cost * 1.4  # 40% markup
        
        data.append({
            'SELL_ID': f'SKU{4000+i+1:04d}',
            'PRODUCT_NAME': p['name'],
            'CATEGORY_NAME': p['category'],
            'SUBCATEGORY_NAME': p['subcategory'],
            'SHELF_SPACE_CM': p['shelf_cm'],
            'UNIT_COST': round(unit_cost, 2),
            'SELLING_PRICE': round(selling_price, 2),
            'CREATED_AT': datetime.now().isoformat()
        })
    
    return pd.DataFrame(data)

# Generate and show the data
product_features_pd = generate_product_features()
print(f"📦 Generated features for {len(product_features_pd)} products")
display(product_features_pd)

# COMMAND ----------

# DBTITLE 1,Create Product Features Table
# Convert to Spark DataFrame
product_features_df = spark.createDataFrame(product_features_pd)

# Create the feature table
# Note: SELL_ID is the primary key for lookups
fe.create_table(
    name=PRODUCT_FEATURES_PATH,
    primary_keys=["SELL_ID"],
    df=product_features_df,
    description="Product features for stock optimization including costs, categories, and shelf space allocation"
)

print(f"✅ Created feature table: {PRODUCT_FEATURES_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Feature Table 2: Demand Features
# MAGIC 
# MAGIC This table contains **time-varying demand metrics** for each product:
# MAGIC - Average daily demand
# MAGIC - Demand standard deviation (volatility)
# MAGIC - 30-day demand forecast
# MAGIC - Last updated timestamp

# COMMAND ----------

# DBTITLE 1,Generate Demand Features Data
def generate_demand_features(product_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate realistic demand forecasts based on product characteristics.
    
    In production, this would be computed from historical sales data and ML forecasts.
    """
    np.random.seed(42)
    
    # Category-based demand multipliers (units per day per cm of shelf space)
    category_demand = {
        'Beer & Seltzer': 8.0,   # High volume
        'Hot Sauce': 2.5,        # Lower volume  
        'Ice Cream': 5.0,        # Medium-high volume
    }
    
    # Subcategory variance multipliers
    subcategory_variance = {
        'Craft Beer': 0.35,
        'Hard Seltzer': 0.25,
        'Asian Style': 0.20,
        'Louisiana Style': 0.15,
        'Mexican Style': 0.20,
        'Extreme Heat': 0.50,
        'Craft/Artisan': 0.40,
        'Premium Pints': 0.30,
        'Premium Tubs': 0.25,
        'Low-Cal Pints': 0.35,
        'Sticks/Bars': 0.20,
    }
    
    demand_data = []
    for _, row in product_df.iterrows():
        # Base demand from shelf space and category
        demand_multiplier = category_demand.get(row['CATEGORY_NAME'], 3.0)
        base_demand = row['SHELF_SPACE_CM'] * demand_multiplier
        
        # Add random variation
        avg_daily_demand = base_demand * np.random.uniform(0.8, 1.2)
        
        # Calculate standard deviation based on subcategory
        variance_mult = subcategory_variance.get(row['SUBCATEGORY_NAME'], 0.25)
        demand_std = avg_daily_demand * variance_mult
        
        # 30-day forecast
        total_forecast_30d = avg_daily_demand * 30
        
        demand_data.append({
            'SELL_ID': row['SELL_ID'],
            'AVG_DAILY_DEMAND': round(avg_daily_demand, 2),
            'DEMAND_STD': round(demand_std, 2),
            'TOTAL_FORECAST_30D': round(total_forecast_30d, 2),
            'FORECAST_DATE': datetime.now().date().isoformat(),
            'UPDATED_AT': datetime.now().isoformat()
        })
    
    return pd.DataFrame(demand_data)

# Generate demand features
demand_features_pd = generate_demand_features(product_features_pd)
print(f"📊 Generated demand forecasts for {len(demand_features_pd)} products")
display(demand_features_pd)

# COMMAND ----------

# DBTITLE 1,Create Demand Features Table
# Convert to Spark DataFrame
demand_features_df = spark.createDataFrame(demand_features_pd)

# Create the feature table
# Note: SELL_ID is the primary key for lookups
fe.create_table(
    name=DEMAND_FEATURES_PATH,
    primary_keys=["SELL_ID"],
    df=demand_features_df,
    description="Demand forecast features for stock optimization including average demand, volatility, and forecasts"
)

print(f"✅ Created feature table: {DEMAND_FEATURES_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Verify Feature Tables

# COMMAND ----------

# DBTITLE 1,Query Product Features
print("📦 Product Features:")
display(spark.table(PRODUCT_FEATURES_PATH))

# COMMAND ----------

# DBTITLE 1,Query Demand Features
print("📊 Demand Features:")
display(spark.table(DEMAND_FEATURES_PATH))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Feature Statistics

# COMMAND ----------

# DBTITLE 1,Summary Statistics
print("="*60)
print("📈 FEATURE TABLE STATISTICS")
print("="*60)

# Product features
product_count = spark.table(PRODUCT_FEATURES_PATH).count()
avg_cost = spark.table(PRODUCT_FEATURES_PATH).selectExpr("avg(UNIT_COST) as avg_cost").first()['avg_cost']
avg_price = spark.table(PRODUCT_FEATURES_PATH).selectExpr("avg(SELLING_PRICE) as avg_price").first()['avg_price']

print(f"\n📦 Product Features ({PRODUCT_FEATURES_PATH}):")
print(f"   Total Products: {product_count}")
print(f"   Average Unit Cost: ${avg_cost:.2f}")
print(f"   Average Selling Price: ${avg_price:.2f}")
print(f"   Average Markup: {((avg_price/avg_cost - 1)*100):.1f}%")

# Demand features
demand_count = spark.table(DEMAND_FEATURES_PATH).count()
total_daily_demand = spark.table(DEMAND_FEATURES_PATH).selectExpr("sum(AVG_DAILY_DEMAND) as total").first()['total']
avg_demand_std = spark.table(DEMAND_FEATURES_PATH).selectExpr("avg(DEMAND_STD) as avg_std").first()['avg_std']

print(f"\n📊 Demand Features ({DEMAND_FEATURES_PATH}):")
print(f"   Total Products: {demand_count}")
print(f"   Total Daily Demand: {total_daily_demand:.0f} units")
print(f"   Average Demand Volatility (σ): {avg_demand_std:.2f}")

# By category
print(f"\n📁 Demand by Category:")
category_stats = spark.sql(f"""
    SELECT 
        p.CATEGORY_NAME,
        COUNT(*) as product_count,
        SUM(d.AVG_DAILY_DEMAND) as total_daily_demand,
        AVG(d.DEMAND_STD) as avg_volatility
    FROM {PRODUCT_FEATURES_PATH} p
    JOIN {DEMAND_FEATURES_PATH} d ON p.SELL_ID = d.SELL_ID
    GROUP BY p.CATEGORY_NAME
    ORDER BY total_daily_demand DESC
""").collect()

for row in category_stats:
    print(f"   • {row['CATEGORY_NAME']}:")
    print(f"      Products: {row['product_count']}")
    print(f"      Daily Demand: {row['total_daily_demand']:.0f} units")
    print(f"      Avg Volatility: {row['avg_volatility']:.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🎉 Complete!
# MAGIC 
# MAGIC **Feature tables successfully created in Unity Catalog!**
# MAGIC 
# MAGIC | Table | Path | Primary Key |
# MAGIC |-------|------|-------------|
# MAGIC | Product Features | `{PRODUCT_FEATURES_PATH}` | `SELL_ID` |
# MAGIC | Demand Features | `{DEMAND_FEATURES_PATH}` | `SELL_ID` |
# MAGIC 
# MAGIC ### Next Steps
# MAGIC 
# MAGIC 1. **Train Model**: Run `01_train_stock_optimizer` notebook to train a model using these features
# MAGIC 2. **Update Features**: Use `fe.write_table()` to update demand forecasts periodically
# MAGIC 3. **Feature Lineage**: View feature lineage in Catalog Explorer
# MAGIC 
# MAGIC ### Feature Updates (Production)
# MAGIC 
# MAGIC In production, you would update demand features regularly:
# MAGIC 
# MAGIC ```python
# MAGIC # Update demand features with new forecasts
# MAGIC fe.write_table(
# MAGIC     name=DEMAND_FEATURES_PATH,
# MAGIC     df=new_demand_forecasts_df,
# MAGIC     mode='merge'
# MAGIC )
# MAGIC ```
