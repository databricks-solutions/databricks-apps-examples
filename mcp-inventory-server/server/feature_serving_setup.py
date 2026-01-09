"""
Auto-Setup for Feature Serving

This module automatically initializes Feature Serving infrastructure
when the MCP server starts. It runs setup tasks lazily on first use.
"""

import datetime
import time
from typing import Optional, Tuple
import os


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [FEATURE-SETUP] {message}")


class FeatureServingManager:
    """
    Manages Feature Serving infrastructure with automatic setup.
    
    On first use, it will:
    1. Check if feature tables exist
    2. Create them if needed with sample data
    3. Set up Feature Serving endpoint
    4. Cache the status for subsequent calls
    """
    
    def __init__(self):
        self._initialized = False
        self._feature_serving_available = False
        self._initialization_attempted = False
        self._use_fallback = os.environ.get("FEATURE_SERVING_FALLBACK", "true").lower() == "true"
    
    def is_available(self) -> bool:
        """Check if Feature Serving is available"""
        if not self._initialization_attempted:
            self._initialize()
        return self._feature_serving_available
    
    def _check_feature_tables_exist(self) -> bool:
        """Check if feature tables exist"""
        try:
            from server import utils
            
            tables = [
                'excel_app.product_demand_features',
                'excel_app.product_cost_features',
                'excel_app.current_inventory'
            ]
            
            for table in tables:
                try:
                    query = f"SELECT COUNT(*) as cnt FROM {table} LIMIT 1"
                    result = utils.execute_query(query)
                    if not result or result[0]['cnt'] == 0:
                        log(f"⚠️  Table {table} is empty")
                        return False
                except Exception:
                    log(f"⚠️  Table {table} doesn't exist")
                    return False
            
            log("✓ All feature tables exist and have data")
            return True
            
        except Exception as e:
            log(f"⚠️  Error checking feature tables: {e}")
            return False
    
    def _create_feature_tables(self) -> bool:
        """Create feature tables with initial sample data"""
        try:
            log("→ Creating feature tables...")
            from server import utils
            
            # Create product_demand_features (PostgreSQL syntax)
            create_demand = """
                CREATE TABLE IF NOT EXISTS excel_app.product_demand_features (
                    sell_id VARCHAR(100) PRIMARY KEY,
                    avg_daily_demand DOUBLE PRECISION,
                    demand_std DOUBLE PRECISION,
                    total_forecast_30d DOUBLE PRECISION,
                    seasonal_factor DOUBLE PRECISION,
                    trend_factor DOUBLE PRECISION,
                    last_updated TIMESTAMP
                )
            """
            utils.execute_query(create_demand)
            
            # Create product_cost_features (PostgreSQL syntax)
            create_cost = """
                CREATE TABLE IF NOT EXISTS excel_app.product_cost_features (
                    sell_id VARCHAR(100) PRIMARY KEY,
                    unit_cost DOUBLE PRECISION,
                    selling_price DOUBLE PRECISION,
                    holding_cost_rate DOUBLE PRECISION,
                    ordering_cost DOUBLE PRECISION,
                    last_updated TIMESTAMP
                )
            """
            utils.execute_query(create_cost)
            
            # Create current_inventory (PostgreSQL syntax)
            create_inventory = """
                CREATE TABLE IF NOT EXISTS excel_app.current_inventory (
                    sell_id VARCHAR(100) PRIMARY KEY,
                    current_stock INTEGER,
                    safety_stock INTEGER,
                    last_order_date DATE,
                    last_updated TIMESTAMP
                )
            """
            utils.execute_query(create_inventory)
            
            log("✓ Feature tables created")
            
            # Populate with initial data
            return self._populate_initial_features()
            
        except Exception as e:
            log(f"❌ Error creating feature tables: {e}")
            return False
    
    def _populate_initial_features(self) -> bool:
        """Populate feature tables with initial sample data"""
        try:
            log("→ Populating initial feature data...")
            from server import utils
            
            # Get products from layout_data
            query = 'SELECT "SELL_ID" FROM excel_app.layout_data'
            products = utils.execute_query(query)
            
            if not products:
                log("⚠️  No products in layout_data")
                return False
            
            timestamp = datetime.datetime.now().isoformat()
            
            # Prepare feature records
            demand_features = []
            cost_features = []
            inventory_features = []
            
            for product in products:
                sell_id = product['SELL_ID']
                base_demand = 50.0
                
                demand_features.append({
                    'sell_id': sell_id,
                    'avg_daily_demand': base_demand,
                    'demand_std': base_demand * 0.2,
                    'total_forecast_30d': base_demand * 30,
                    'seasonal_factor': 1.0,
                    'trend_factor': 1.0,
                    'last_updated': timestamp
                })
                
                cost_features.append({
                    'sell_id': sell_id,
                    'unit_cost': 10.0,
                    'selling_price': 20.0,
                    'holding_cost_rate': 0.2,
                    'ordering_cost': 50.0,
                    'last_updated': timestamp
                })
                
                inventory_features.append({
                    'sell_id': sell_id,
                    'current_stock': 100,
                    'safety_stock': int(base_demand * 3),
                    'last_order_date': datetime.date.today().isoformat(),
                    'last_updated': timestamp
                })
            
            # Insert data
            utils.batch_insert('excel_app.product_demand_features', demand_features, overwrite=True)
            utils.batch_insert('excel_app.product_cost_features', cost_features, overwrite=True)
            utils.batch_insert('excel_app.current_inventory', inventory_features, overwrite=True)
            
            log(f"✓ Populated {len(products)} products with initial features")
            return True
            
        except Exception as e:
            log(f"❌ Error populating features: {e}")
            return False
    
    def _check_feature_serving_endpoint(self) -> bool:
        """Check if Feature Serving endpoint exists and is ready"""
        try:
            from databricks.sdk import WorkspaceClient
            
            w = WorkspaceClient()
            endpoint = w.serving_endpoints.get(name="stock-optimization-features")
            
            if endpoint.state.ready == "READY":
                log("✓ Feature Serving endpoint is ready")
                return True
            else:
                log(f"⚠️  Feature Serving endpoint state: {endpoint.state.ready}")
                return False
                
        except Exception as e:
            log(f"⚠️  Feature Serving endpoint not available: {e}")
            return False
    
    def _initialize(self) -> None:
        """
        Initialize Feature Serving infrastructure.
        
        This is called lazily on first use. It checks if everything is set up
        and creates missing components if needed.
        
        For Lakebase (PostgreSQL), we use direct table queries instead of endpoints.
        """
        self._initialization_attempted = True
        
        log("Initializing Feature Serving...")
        
        # Step 1: Check if feature tables exist
        if not self._check_feature_tables_exist():
            log("→ Feature tables not found, creating them...")
            if not self._create_feature_tables():
                log("⚠️  Could not create feature tables, using fallback")
                self._feature_serving_available = False
                return
        
        # Step 2: For Lakebase, we query tables directly (no endpoint needed)
        # Check if Feature Serving endpoint exists (optional for Unity Catalog)
        endpoint_available = self._check_feature_serving_endpoint()
        if endpoint_available:
            log("✅ Feature Serving endpoint is available (will use it)")
        else:
            log("ℹ️  No Feature Serving endpoint (querying tables directly)")
        
        # Feature tables exist, so we're ready!
        log("✅ Feature Serving is fully initialized and ready")
        self._initialized = True
        self._feature_serving_available = True
    
    def get_features(self, sell_ids: list) -> Tuple[Optional[list], str]:
        """
        Get features for the given sell_ids.
        
        For Lakebase (PostgreSQL), we query feature tables directly.
        For Unity Catalog, we would use a Feature Serving endpoint.
        
        Returns:
            Tuple of (features list, method used)
            - If features available, returns (features, "feature_tables")
            - If not, returns (None, "fallback") to use dummy feature generation
        """
        if not self.is_available():
            return None, "fallback"
        
        try:
            from server import utils
            
            # Query features directly from PostgreSQL tables
            # Build a query to join all feature tables
            placeholders = ','.join(['%s'] * len(sell_ids))
            
            query = f"""
                SELECT 
                    d.sell_id,
                    d.avg_daily_demand,
                    d.demand_std,
                    d.total_forecast_30d,
                    d.seasonal_factor,
                    d.trend_factor,
                    c.unit_cost,
                    c.selling_price,
                    c.holding_cost_rate,
                    c.ordering_cost,
                    i.current_stock,
                    i.safety_stock
                FROM excel_app.product_demand_features d
                INNER JOIN excel_app.product_cost_features c ON d.sell_id = c.sell_id
                INNER JOIN excel_app.current_inventory i ON d.sell_id = i.sell_id
                WHERE d.sell_id IN ({placeholders})
            """
            
            features = utils.execute_query(query, tuple(sell_ids))
            
            if not features:
                log("⚠️  No features found for the given sell_ids")
                return None, "fallback"
            
            log(f"✓ Retrieved {len(features)} feature records from feature tables")
            return features, "feature_tables"
            
        except Exception as e:
            log(f"⚠️  Feature table query failed: {e}")
            import traceback
            traceback.print_exc()
            # Mark as unavailable to avoid repeated failed attempts
            self._feature_serving_available = False
            return None, "fallback"


# Global instance
_feature_serving_manager: Optional[FeatureServingManager] = None


def get_feature_serving_manager() -> FeatureServingManager:
    """Get the global FeatureServingManager instance"""
    global _feature_serving_manager
    if _feature_serving_manager is None:
        _feature_serving_manager = FeatureServingManager()
    return _feature_serving_manager


def auto_initialize_on_startup():
    """
    Call this when the MCP server starts to initialize Feature Serving in background.
    This ensures the first optimization request doesn't have to wait for setup.
    """
    log("Starting Feature Serving auto-initialization...")
    
    try:
        manager = get_feature_serving_manager()
        # Trigger initialization in background
        is_available = manager.is_available()
        
        if is_available:
            log("✅ Feature Serving initialized successfully")
        else:
            log("⚠️  Feature Serving not available, will use fallback")
            log("   To enable Feature Serving, run setup scripts:")
            log("   1. uv run python scripts/create_feature_spec.py")
            log("   2. uv run python scripts/create_feature_serving_endpoint.py")
    
    except Exception as e:
        log(f"⚠️  Auto-initialization failed: {e}")
        log("   System will use fallback feature generation")


if __name__ == "__main__":
    # Test the auto-initialization
    log("=" * 70)
    log("TESTING FEATURE SERVING AUTO-INITIALIZATION")
    log("=" * 70)
    
    auto_initialize_on_startup()
    
    # Test feature retrieval
    manager = get_feature_serving_manager()
    
    from server import utils
    query = 'SELECT "SELL_ID" FROM excel_app.layout_data LIMIT 2'
    products = utils.execute_query(query)
    
    if products:
        sell_ids = [p['SELL_ID'] for p in products]
        features, method = manager.get_features(sell_ids)
        
        log(f"Feature retrieval method: {method}")
        if features:
            log(f"Retrieved {len(features)} feature records")
        else:
            log("Using fallback feature generation")

