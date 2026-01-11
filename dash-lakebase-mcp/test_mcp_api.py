#!/usr/bin/env python3
"""
Quick test script for MCP API endpoints.

Usage:
    python test_mcp_api.py
"""

import requests
import json

MCP_URL = "http://localhost:9000"


def test_root():
    """Test root endpoint"""
    print("\n🧪 Testing GET /")
    response = requests.get(f"{MCP_URL}/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("   ✅ PASS")


def test_health():
    """Test health endpoint"""
    print("\n🧪 Testing GET /health")
    response = requests.get(f"{MCP_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("   ✅ PASS")


def test_validation_empty():
    """Test validation with empty data"""
    print("\n🧪 Testing POST /api/validate (empty data)")
    response = requests.post(
        f"{MCP_URL}/api/validate",
        json={"data": []}
    )
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Valid: {result['valid']}")
    print(f"   Has Errors: {result['has_errors']}")
    print(f"   Summary: {result['summary']}")
    assert response.status_code == 200
    assert result["valid"] == False
    assert result["has_errors"] == True
    print("   ✅ PASS")


def test_validation_valid_data():
    """Test validation with valid data"""
    print("\n🧪 Testing POST /api/validate (valid data)")
    data = [{
        "SKU_ID": "SKU001",
        "SKU_NAME": "Test Product",
        "CATEGORY": "Beer & Seltzer",
        "STATUS": "active",
        "WEEKLY_UNITS": 100,
        "CURRENT_FACINGS": 5,
        "PACK_WIDTH_MM": 80
    }]
    response = requests.post(
        f"{MCP_URL}/api/validate",
        json={"data": data}
    )
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Valid: {result['valid']}")
    print(f"   Has Errors: {result['has_errors']}")
    print(f"   Has Warnings: {result['has_warnings']}")
    print(f"   Summary: {result['summary']}")
    assert response.status_code == 200
    assert result["valid"] == True
    assert result["has_errors"] == False
    print("   ✅ PASS")


def test_validation_invalid_data():
    """Test validation with invalid data"""
    print("\n🧪 Testing POST /api/validate (invalid data)")
    data = [{
        "SKU_ID": "SKU001",
        # Missing required fields
        "WEEKLY_UNITS": "not a number",  # Invalid type
        "CURRENT_FACINGS": -5,  # Negative value
    }]
    response = requests.post(
        f"{MCP_URL}/api/validate",
        json={"data": data}
    )
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Valid: {result['valid']}")
    print(f"   Has Errors: {result['has_errors']}")
    print(f"   Issues: {len(result['issues'])} found")
    for issue in result['issues'][:3]:
        print(f"     - {issue['severity']}: {issue['message']}")
    assert response.status_code == 200
    assert result["valid"] == False
    assert result["has_errors"] == True
    assert len(result["issues"]) > 0
    print("   ✅ PASS")


def test_validation_duplicate_skus():
    """Test validation with duplicate SKU IDs"""
    print("\n🧪 Testing POST /api/validate (duplicate SKUs)")
    data = [
        {
            "SKU_ID": "SKU001",
            "SKU_NAME": "Product 1",
            "CATEGORY": "Beer & Seltzer",
            "STATUS": "active",
            "WEEKLY_UNITS": 100,
            "CURRENT_FACINGS": 5,
            "PACK_WIDTH_MM": 80
        },
        {
            "SKU_ID": "SKU001",  # Duplicate!
            "SKU_NAME": "Product 2",
            "CATEGORY": "Hot Sauce",
            "STATUS": "active",
            "WEEKLY_UNITS": 50,
            "CURRENT_FACINGS": 3,
            "PACK_WIDTH_MM": 60
        }
    ]
    response = requests.post(
        f"{MCP_URL}/api/validate",
        json={"data": data}
    )
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Valid: {result['valid']}")
    print(f"   Has Errors: {result['has_errors']}")
    duplicate_errors = [i for i in result['issues'] if 'Duplicate' in i['message']]
    print(f"   Duplicate errors: {len(duplicate_errors)}")
    assert response.status_code == 200
    assert result["valid"] == False
    assert len(duplicate_errors) > 0
    print("   ✅ PASS")


def main():
    """Run all tests"""
    print("=" * 60)
    print("MCP API Test Suite")
    print("=" * 60)
    
    try:
        test_root()
        test_health()
        test_validation_empty()
        test_validation_valid_data()
        test_validation_invalid_data()
        test_validation_duplicate_skus()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to MCP server")
        print(f"   Make sure the server is running at {MCP_URL}")
        print("   Start it with: cd mcp_app && uv run uvicorn range_optimizer.backend.app:app --reload --port 9000")
        return 1
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
