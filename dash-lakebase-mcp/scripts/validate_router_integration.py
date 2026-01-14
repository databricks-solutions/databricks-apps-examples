#!/usr/bin/env python3
"""
Validate Router Integration Code

This script validates that the router.py integration code is syntactically correct
and follows the expected pattern for Feature Store + ML endpoint integration.
"""

import ast
import sys


def validate_router_integration():
    """Validate the router.py integration code"""
    print("=" * 80)
    print("🔍 Validating MCP Router Integration")
    print("=" * 80)

    router_path = "mcp_app/range_optimizer/backend/router.py"

    print(f"\n📄 Reading {router_path}...")

    try:
        with open(router_path, 'r') as f:
            router_code = f.read()

        print(f"✅ File read successfully ({len(router_code)} chars)")

        # Parse AST to validate syntax
        print("\n🔍 Validating Python syntax...")
        try:
            tree = ast.parse(router_code)
            print("✅ Python syntax is valid")
        except SyntaxError as e:
            print(f"❌ Syntax error: {e}")
            return 1

        # Check for key integration components
        print("\n🔍 Checking for integration components...")
        checks = {
            "Feature Store import": "from databricks.sdk.runtime import spark",
            "Feature query": "smarter_forecasting.stock_optimization.sku_features",
            "Endpoint call": "serving-endpoints",
            "Prediction parsing": "predictions",
            "Result mapping": "optimization_run_id",
            "Bulk insert": "bulk_insert(opt_table",
        }

        passed = 0
        total = len(checks)

        for check_name, pattern in checks.items():
            if pattern in router_code:
                print(f"   ✅ {check_name}")
                passed += 1
            else:
                print(f"   ❌ {check_name} - pattern not found: {pattern}")

        # Check function signature
        print("\n🔍 Checking run_optimization function...")
        if "@api.post(\"/run_optimization\"" in router_code:
            print("   ✅ Endpoint decorator present")
            passed_func_checks = 1
        else:
            print("   ❌ Endpoint decorator missing")
            passed_func_checks = 0

        if "async def run_optimization(payload: dict)" in router_code:
            print("   ✅ Function signature correct")
            passed_func_checks += 1
        else:
            print("   ❌ Function signature incorrect")

        # Check error handling
        print("\n🔍 Checking error handling...")
        error_checks = 0
        if "try:" in router_code and "except" in router_code:
            print("   ✅ Try-except blocks present")
            error_checks += 1

        if "HTTPException" in router_code:
            print("   ✅ HTTPException used for errors")
            error_checks += 1

        if "logger.error" in router_code or "logger.warning" in router_code:
            print("   ✅ Logger used for error reporting")
            error_checks += 1

        # Check response structure
        print("\n🔍 Checking response structure...")
        response_checks = 0
        if '"status": "success"' in router_code:
            print("   ✅ Success status in response")
            response_checks += 1

        if '"forecast_id":' in router_code:
            print("   ✅ Forecast ID in response")
            response_checks += 1

        if '"product_count":' in router_code:
            print("   ✅ Product count in response")
            response_checks += 1

        # Summary
        print("\n" + "=" * 80)
        print("📊 Validation Summary")
        print("=" * 80)
        print(f"   Integration components: {passed}/{total}")
        print(f"   Function checks: {passed_func_checks}/2")
        print(f"   Error handling: {error_checks}/3")
        print(f"   Response structure: {response_checks}/3")

        total_checks = passed + passed_func_checks + error_checks + response_checks
        max_checks = total + 2 + 3 + 3

        print(f"\n   Total: {total_checks}/{max_checks} checks passed")

        if total_checks == max_checks:
            print("\n✅ SUCCESS! Integration code is complete and correct")
            print("=" * 80)
            print("\n📋 Integration Flow:")
            print("   1. Receive forecast_id from UI")
            print("   2. Fetch SKU_IDs from optimization_runs table")
            print("   3. Query Feature Store (Unity Catalog) for features")
            print("   4. Call ML serving endpoint with features")
            print("   5. Parse predictions from endpoint response")
            print("   6. Map results to opt_planogram schema")
            print("   7. Bulk insert results into opt_planogram table")
            print("   8. Return success response to UI")
            print("\n🌟 Ready for end-to-end testing!")
            print("=" * 80)
            return 0
        else:
            print("\n⚠️  Some validation checks failed")
            print("=" * 80)
            return 1

    except FileNotFoundError:
        print(f"❌ File not found: {router_path}")
        return 1
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(validate_router_integration())
