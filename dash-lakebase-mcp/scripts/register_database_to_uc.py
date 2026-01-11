"""
Register Lakebase database to Unity Catalog

This script registers the existing Lakebase database instance as a Unity Catalog catalog,
enabling UC privileges for data access management and integration with managed syncing.

Prerequisites:
- Databricks workspace with access to the database instance
- CREATE CATALOG privileges on the Unity Catalog metastore
- Database instance must be running

References:
- https://docs.databricks.com/aws/en/oltp/instances/register-uc?language=Python+SDK
"""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseCatalog


def register_database_catalog(
    instance_name: str = "daveok",
    database_name: str = "databricks_postgres",
    catalog_name: str = "range_optimizer_catalog",
):
    """
    Register the Lakebase database as a Unity Catalog catalog.
    
    Args:
        instance_name: Name of the Lakebase database instance
        database_name: Name of the Postgres database to register
        catalog_name: Desired name for the Unity Catalog catalog
    """
    # Initialize the Workspace client
    w = WorkspaceClient()
    
    print(f"🔄 Registering database '{database_name}' from instance '{instance_name}' as UC catalog '{catalog_name}'...")
    
    try:
        # Register the existing database as a UC catalog
        catalog = w.database.create_database_catalog(
            DatabaseCatalog(
                name=catalog_name,                    # Name of the UC catalog to create
                database_instance_name=instance_name, # Name of the database instance
                database_name=database_name,          # Name of the existing Postgres database
            )
        )
        print(f"✅ Successfully created database catalog: {catalog.name}")
        print(f"\n📊 Catalog Details:")
        print(f"   - Catalog Name: {catalog.name}")
        print(f"   - Database Instance: {instance_name}")
        print(f"   - Database Name: {database_name}")
        print(f"\n💡 Next Steps:")
        print(f"   1. Navigate to Catalog in your Databricks workspace")
        print(f"   2. Attach a serverless SQL warehouse")
        print(f"   3. Explore schemas and tables in '{catalog_name}'")
        print(f"   4. Tables will sync automatically as you browse")
        
        return catalog
        
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"ℹ️  Catalog '{catalog_name}' already exists")
            print(f"   Verifying existing catalog...")
            try:
                existing_catalog = w.database.get_database_catalog(name=catalog_name)
                print(f"✅ Verified existing catalog: {existing_catalog.name}")
                return existing_catalog
            except Exception as verify_error:
                print(f"❌ Error verifying catalog: {verify_error}")
                raise
        else:
            print(f"❌ Error creating database catalog: {e}")
            raise


def list_database_catalogs(instance_name: str = "daveok"):
    """List all existing database catalogs for a given instance in Unity Catalog."""
    w = WorkspaceClient()
    
    print(f"\n📋 Listing database catalogs for instance '{instance_name}'...")
    try:
        catalogs = w.database.list_database_catalogs(instance_name=instance_name)
        catalog_list = list(catalogs)
        
        if catalog_list:
            print(f"Found {len(catalog_list)} database catalog(s):")
            for cat in catalog_list:
                print(f"   - {cat.name} (Instance: {cat.database_instance_name}, DB: {cat.database_name})")
        else:
            print("   No database catalogs found")
            
        return catalog_list
    except Exception as e:
        print(f"❌ Error listing catalogs: {e}")
        return []


def main():
    """Main function to register database and list catalogs."""
    print("=" * 70)
    print("  Databricks Lakebase → Unity Catalog Registration")
    print("=" * 70)
    
    # List existing catalogs first
    existing_catalogs = list_database_catalogs()
    
    # Register the database as a catalog
    print("\n" + "=" * 70)
    catalog = register_database_catalog(
        instance_name="daveok",
        database_name="databricks_postgres",
        catalog_name="range_optimizer_catalog",
    )
    
    print("\n" + "=" * 70)
    print("✅ Registration complete!")
    print("=" * 70)
    
    return catalog


if __name__ == "__main__":
    main()
