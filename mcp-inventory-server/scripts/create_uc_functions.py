"""
Create Unity Catalog Functions for Feature Engineering

This script creates UC functions that can be used in the FeatureSpec
for derived feature calculations.
"""

import datetime


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [UC-FUNCTIONS] {message}")


def create_uc_functions():
    """Create Unity Catalog functions for feature transformations"""
    
    log("Creating Unity Catalog functions...")
    
    try:
        from unitycatalog.ai.core.databricks import DatabricksFunctionClient
        
        client = DatabricksFunctionClient()
        
        # Function 1: Calculate reorder urgency
        def calculate_reorder_urgency(
            current_stock: float, 
            avg_daily_demand: float, 
            safety_stock: float
        ) -> float:
            """
            Calculate how urgently a product needs reordering.
            
            Returns a score from 0 (no urgency) to 1 (critical).
            
            Args:
                current_stock: Current stock level
                avg_daily_demand: Average daily demand
                safety_stock: Safety stock level
                
            Returns:
                Urgency score between 0 and 1
            """
            if avg_daily_demand <= 0:
                return 0.0
            
            days_of_stock = current_stock / avg_daily_demand
            
            if days_of_stock <= 2:
                return 1.0  # Critical
            elif days_of_stock <= 7:
                return 0.7  # High urgency
            elif days_of_stock <= 14:
                return 0.3  # Medium urgency
            else:
                return 0.0  # No urgency
        
        log("→ Creating function: calculate_reorder_urgency")
        client.create_python_function(
            func=calculate_reorder_urgency,
            catalog="main",
            schema="excel_app",
            replace=True
        )
        log("✓ Function created: calculate_reorder_urgency")
        
        # Function 2: Calculate lead time demand
        def calculate_lead_time_demand(
            avg_daily_demand: float,
            lead_time_days: float = 7.0
        ) -> float:
            """
            Calculate expected demand during lead time.
            
            Args:
                avg_daily_demand: Average daily demand
                lead_time_days: Lead time in days (default 7)
                
            Returns:
                Expected demand during lead time
            """
            return avg_daily_demand * lead_time_days
        
        log("→ Creating function: calculate_lead_time_demand")
        client.create_python_function(
            func=calculate_lead_time_demand,
            catalog="main",
            schema="excel_app",
            replace=True
        )
        log("✓ Function created: calculate_lead_time_demand")
        
        # Function 3: Calculate profit margin
        def calculate_profit_margin(
            selling_price: float,
            unit_cost: float
        ) -> float:
            """
            Calculate profit margin percentage.
            
            Args:
                selling_price: Selling price per unit
                unit_cost: Cost per unit
                
            Returns:
                Profit margin as a decimal (e.g., 0.5 for 50%)
            """
            if selling_price <= 0:
                return 0.0
            return (selling_price - unit_cost) / selling_price
        
        log("→ Creating function: calculate_profit_margin")
        client.create_python_function(
            func=calculate_profit_margin,
            catalog="main",
            schema="excel_app",
            replace=True
        )
        log("✓ Function created: calculate_profit_margin")
        
        log("✅ All UC functions created successfully!")
        
    except ImportError:
        log("❌ unitycatalog.ai package not installed")
        log("   Install with: pip install unitycatalog-ai")
        raise
    except Exception as e:
        log(f"❌ Error creating UC functions: {e}")
        import traceback
        traceback.print_exc()
        raise


def verify_functions():
    """Verify that UC functions were created"""
    
    log("Verifying UC functions...")
    
    from databricks.sdk import WorkspaceClient
    
    try:
        w = WorkspaceClient()
        
        functions = [
            "main.excel_app.calculate_reorder_urgency",
            "main.excel_app.calculate_lead_time_demand",
            "main.excel_app.calculate_profit_margin",
        ]
        
        for func_name in functions:
            try:
                func_info = w.functions.get(name=func_name)
                log(f"✓ {func_name}: {func_info.comment or 'Available'}")
            except Exception as e:
                log(f"⚠️  {func_name}: Not found or error - {e}")
        
        log("✓ Function verification complete")
        
    except Exception as e:
        log(f"⚠️  Verification error: {e}")


def main():
    """Main function"""
    log("=" * 70)
    log("UNITY CATALOG FUNCTIONS SETUP")
    log("=" * 70)
    
    create_uc_functions()
    verify_functions()
    
    log("=" * 70)
    log("UC FUNCTIONS SETUP COMPLETE!")
    log("=" * 70)


if __name__ == "__main__":
    main()

