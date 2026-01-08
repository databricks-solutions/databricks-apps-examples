"""
Setup Unity Catalog for Coles Inventory Intelligence
Creates catalog and schema with proper storage configuration
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import CatalogInfo, SchemaInfo

def setup_unity_catalog():
    """Setup Unity Catalog with proper storage"""
    print("=" * 70)
    print("SETTING UP UNITY CATALOG FOR COLES INVENTORY INTELLIGENCE")
    print("=" * 70)

    w = WorkspaceClient()
    print(f"✓ Connected to workspace: {w.config.host}")

    catalog_name = "coles_inventory"
    schema_name = "models"

    # Check if catalog exists and get its info
    try:
        existing_catalog = w.catalogs.get(catalog_name)
        print(f"\n✓ Catalog '{catalog_name}' already exists")
        print(f"  Storage root: {existing_catalog.storage_root}")

        # If it doesn't have storage, we need to update it
        if not existing_catalog.storage_root:
            print(f"\n⚠️  Catalog '{catalog_name}' doesn't have storage configured")
            print(f"  This catalog was created without storage_root parameter")
            print(f"  Deleting and recreating with proper storage...")

            # Delete the catalog
            w.catalogs.delete(catalog_name, force=True)
            print(f"✓ Deleted catalog '{catalog_name}'")

            # Recreate with storage
            print(f"\n→ Creating catalog '{catalog_name}' with managed storage...")
            catalog = w.catalogs.create(
                name=catalog_name,
                comment="Catalog for Coles Inventory Intelligence platform - models, forecasts, and optimization results",
                # For managed catalog, Databricks will create storage automatically
                # We don't specify storage_root for managed catalogs
            )
            print(f"✓ Created managed catalog: {catalog_name}")
            if catalog.storage_root:
                print(f"  Storage root: {catalog.storage_root}")
            else:
                print(f"  Storage: Managed by Databricks")

    except Exception as e:
        if "does not exist" in str(e).lower() or "not found" in str(e).lower():
            print(f"\n→ Creating catalog '{catalog_name}'...")
            catalog = w.catalogs.create(
                name=catalog_name,
                comment="Catalog for Coles Inventory Intelligence platform - models, forecasts, and optimization results",
            )
            print(f"✓ Created catalog: {catalog_name}")
            if catalog.storage_root:
                print(f"  Storage root: {catalog.storage_root}")
        else:
            print(f"❌ Error accessing catalog: {e}")
            raise

    # Create schema
    schema_full_name = f"{catalog_name}.{schema_name}"
    try:
        existing_schema = w.schemas.get(schema_full_name)
        print(f"\n✓ Schema '{schema_full_name}' already exists")
        print(f"  Storage location: {existing_schema.storage_root}")
    except Exception as e:
        if "does not exist" in str(e).lower() or "not found" in str(e).lower():
            print(f"\n→ Creating schema '{schema_full_name}'...")
            schema = w.schemas.create(
                name=schema_name,
                catalog_name=catalog_name,
                comment="ML models for stock optimization",
            )
            print(f"✓ Created schema: {schema_full_name}")
            if schema.storage_root:
                print(f"  Storage location: {schema.storage_root}")
        else:
            print(f"❌ Error creating schema: {e}")
            raise

    print("\n" + "=" * 70)
    print("UNITY CATALOG SETUP COMPLETE")
    print("=" * 70)
    print(f"\n✅ Catalog: {catalog_name}")
    print(f"✅ Schema: {schema_full_name}")
    print(f"\n📝 Use this model name for MLflow registration:")
    print(f"   {catalog_name}.{schema_name}.stock_optimization_model")
    print()

if __name__ == "__main__":
    try:
        setup_unity_catalog()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
