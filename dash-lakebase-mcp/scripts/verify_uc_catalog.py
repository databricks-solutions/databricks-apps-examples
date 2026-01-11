"""
Verify Unity Catalog registration and explore the database catalog

This script verifies the Lakebase database catalog registration in Unity Catalog
and explores the available schemas and tables.
"""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import CatalogInfo
from databricks.sdk.core import DatabricksError


def verify_catalog_exists(catalog_name: str = "range_optimizer_catalog"):
    """
    Verify that the catalog exists in Unity Catalog.
    
    Args:
        catalog_name: Name of the Unity Catalog catalog to verify
        
    Returns:
        CatalogInfo object if catalog exists, None otherwise
    """
    w = WorkspaceClient()
    
    print(f"🔍 Verifying catalog '{catalog_name}' exists in Unity Catalog...")
    
    try:
        # Get catalog info from Unity Catalog (not database-specific API)
        catalog = w.catalogs.get(name=catalog_name)
        print(f"✅ Catalog found: {catalog.name}")
        print(f"   - Owner: {catalog.owner}")
        print(f"   - Created: {catalog.created_at}")
        print(f"   - Comment: {catalog.comment or 'None'}")
        return catalog
        
    except DatabricksError as e:
        if "does not exist" in str(e).lower() or "not found" in str(e).lower():
            print(f"❌ Catalog '{catalog_name}' not found")
        else:
            print(f"❌ Error checking catalog: {e}")
        return None


def list_schemas(catalog_name: str = "range_optimizer_catalog"):
    """
    List all schemas in the catalog.
    
    Args:
        catalog_name: Name of the Unity Catalog catalog
        
    Returns:
        List of schema names
    """
    w = WorkspaceClient()
    
    print(f"\n📂 Listing schemas in catalog '{catalog_name}'...")
    
    try:
        schemas = w.schemas.list(catalog_name=catalog_name)
        schema_list = list(schemas)
        
        if schema_list:
            print(f"Found {len(schema_list)} schema(s):")
            for schema in schema_list:
                print(f"   - {schema.name}")
                if schema.comment:
                    print(f"     Comment: {schema.comment}")
            return [s.name for s in schema_list]
        else:
            print("   No schemas found (they may sync automatically when browsed)")
            return []
            
    except Exception as e:
        print(f"❌ Error listing schemas: {e}")
        return []


def list_tables(catalog_name: str = "range_optimizer_catalog", schema_name: str = None):
    """
    List all tables in a schema or catalog.
    
    Args:
        catalog_name: Name of the Unity Catalog catalog
        schema_name: Optional schema name to filter tables
        
    Returns:
        List of table names
    """
    w = WorkspaceClient()
    
    if schema_name:
        print(f"\n📊 Listing tables in '{catalog_name}.{schema_name}'...")
    else:
        print(f"\n📊 Listing all tables in catalog '{catalog_name}'...")
    
    try:
        if schema_name:
            tables = w.tables.list(catalog_name=catalog_name, schema_name=schema_name)
        else:
            # List all tables across all schemas
            tables = []
            schemas = list_schemas(catalog_name)
            for schema in schemas:
                schema_tables = w.tables.list(catalog_name=catalog_name, schema_name=schema)
                tables.extend(schema_tables)
        
        table_list = list(tables)
        
        if table_list:
            print(f"Found {len(table_list)} table(s):")
            for table in table_list:
                full_name = f"{table.catalog_name}.{table.schema_name}.{table.name}"
                print(f"   - {full_name}")
                print(f"     Type: {table.table_type}")
                if table.comment:
                    print(f"     Comment: {table.comment}")
            return [f"{t.catalog_name}.{t.schema_name}.{t.name}" for t in table_list]
        else:
            print("   No tables found yet")
            print("   💡 Tip: Tables sync automatically when you browse them in Catalog Explorer")
            return []
            
    except Exception as e:
        print(f"❌ Error listing tables: {e}")
        return []


def check_database_catalog(
    instance_name: str = "daveok",
    catalog_name: str = "range_optimizer_catalog"
):
    """
    Check the database catalog registration status.
    
    Args:
        instance_name: Name of the Lakebase database instance
        catalog_name: Name of the Unity Catalog catalog
    """
    w = WorkspaceClient()
    
    print(f"\n🔗 Checking database catalog registration...")
    
    try:
        # Get the database catalog info
        db_catalog = w.database.get_database_catalog(name=catalog_name)
        print(f"✅ Database catalog registered:")
        print(f"   - Catalog Name: {db_catalog.name}")
        print(f"   - Instance Name: {db_catalog.database_instance_name}")
        print(f"   - Database Name: {db_catalog.database_name}")
        
        return db_catalog
        
    except Exception as e:
        print(f"❌ Error checking database catalog: {e}")
        return None


def main():
    """Main function to verify catalog and explore contents."""
    print("=" * 70)
    print("  Unity Catalog Verification - Range Optimizer")
    print("=" * 70)
    
    catalog_name = "range_optimizer_catalog"
    instance_name = "daveok"
    
    # Check database catalog registration
    db_catalog = check_database_catalog(instance_name, catalog_name)
    
    # Verify catalog in Unity Catalog
    catalog = verify_catalog_exists(catalog_name)
    
    if catalog:
        # List schemas
        schemas = list_schemas(catalog_name)
        
        # If schemas exist, explore the first one
        if schemas:
            first_schema = schemas[0]
            list_tables(catalog_name, first_schema)
        else:
            print("\n💡 To trigger schema sync:")
            print(f"   1. Open Catalog Explorer in Databricks workspace")
            print(f"   2. Navigate to '{catalog_name}' catalog")
            print(f"   3. Schemas and tables will sync automatically as you browse")
    
    print("\n" + "=" * 70)
    print("✅ Verification complete!")
    print("=" * 70)
    
    print("\n📍 Access your catalog:")
    print("   Workspace → Catalog → range_optimizer_catalog")
    

if __name__ == "__main__":
    main()
