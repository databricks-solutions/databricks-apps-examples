"""
Verify Unity Catalog Metastore Configuration
Run this after configuring storage to verify everything is ready
"""
from databricks.sdk import WorkspaceClient
import sys

def verify_metastore():
    """Verify Unity Catalog metastore has required storage configuration"""
    print("=" * 70)
    print("VERIFYING UNITY CATALOG METASTORE CONFIGURATION")
    print("=" * 70)

    w = WorkspaceClient()
    print(f"\n✓ Connected to workspace: {w.config.host}")

    # Check metastores
    print("\n→ Checking metastores...")

    # Try to get current metastore (more reliable than list)
    try:
        current_metastore = w.metastores.current()
        print(f"✓ Current metastore: {current_metastore.name}")
        print(f"  ID: {current_metastore.metastore_id}")

        # Check storage configuration
        metastore_details = w.metastores.get(current_metastore.metastore_id)
    except Exception as e:
        print(f"❌ Cannot access current metastore: {e}")
        print("   You may not have metastore admin permissions")
        print("   Attempting to check catalog access anyway...")
        metastore_details = None

    print("\n→ Checking storage configuration...")

    has_storage = False
    has_credential = False

    if metastore_details:
        if metastore_details.storage_root:
            print(f"✓ Storage root configured: {metastore_details.storage_root}")
            has_storage = True
        else:
            print("❌ Storage root NOT configured")
            print("   Set this in: Data → Metastores → Edit → Root storage location")

        if metastore_details.storage_root_credential_id:
            print(f"✓ Storage credential configured: {metastore_details.storage_root_credential_id}")
            has_credential = True
        else:
            print("❌ Storage credential NOT configured")
            print("   Create in: Data → Storage Credentials → Create")
    else:
        print("⚠️  Cannot check metastore storage (insufficient permissions)")
        print("   Contact your Databricks admin to verify storage configuration")

    # Check catalog access
    print("\n→ Checking catalog access...")
    try:
        catalog = w.catalogs.get("coles_inventory")
        print(f"✓ Catalog 'coles_inventory' exists")
        print(f"  Owner: {catalog.owner}")
        if catalog.storage_root:
            print(f"  Storage: {catalog.storage_root}")
    except Exception as e:
        print(f"❌ Cannot access catalog 'coles_inventory': {e}")
        return False

    # Check schema access
    print("\n→ Checking schema access...")
    try:
        schema = w.schemas.get("coles_inventory.models")
        print(f"✓ Schema 'coles_inventory.models' exists")
        print(f"  Owner: {schema.owner}")
        if schema.storage_root:
            print(f"  Storage: {schema.storage_root}")
    except Exception as e:
        print(f"❌ Cannot access schema 'coles_inventory.models': {e}")
        return False

    # Check storage credentials
    print("\n→ Checking storage credentials...")
    try:
        credentials = list(w.storage_credentials.list())
        if credentials:
            print(f"✓ Found {len(credentials)} storage credential(s):")
            for cred in credentials[:3]:  # Show first 3
                print(f"  - {cred.name} ({cred.id})")
        else:
            print("⚠️  No storage credentials found")
            print("   You may need to create one for the metastore")
    except Exception as e:
        print(f"⚠️  Cannot list storage credentials: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    if has_storage and has_credential:
        print("\n✅ Metastore is READY for Unity Catalog model registration!")
        print("\n📝 Next steps:")
        print("   1. Run: uv run python deploy_model_to_mlflow.py")
        print("   2. Wait for model registration to complete")
        print("   3. Deploy endpoint: databricks bundle deploy -t azure-east")
        return True
    else:
        print("\n❌ Metastore is NOT ready")
        print("\n📋 Required actions:")
        if not has_storage:
            print("   ❌ Configure storage root location")
        if not has_credential:
            print("   ❌ Configure storage credential")
        print("\n   See UNITY_CATALOG_SETUP.md for detailed instructions")
        return False

if __name__ == "__main__":
    try:
        success = verify_metastore()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
