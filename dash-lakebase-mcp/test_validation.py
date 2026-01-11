#!/usr/bin/env python3
"""
Test script for Dash AG Grid data validation.

This script demonstrates the validation rules by testing various data scenarios.
Run: uv run python test_validation.py
"""

from typing import List, Dict, Any


def validate_sku_data(data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Simplified version of validation logic for testing.
    Returns dict with 'errors', 'warnings', and 'duplicates' lists.
    """
    errors = []
    warnings = []
    duplicates = []
    
    VALID_STATUSES = {"active", "new", "discontinued"}
    VALID_CATEGORIES = {"Beer & Seltzer", "Hot Sauce", "Ice Cream"}
    
    # Check for duplicates
    sku_id_counts = {}
    for row in data:
        sku_id = row.get("SKU_ID")
        if sku_id:
            sku_id_counts[sku_id] = sku_id_counts.get(sku_id, 0) + 1
    duplicates = [sid for sid, count in sku_id_counts.items() if count > 1]
    
    # Validate each row
    for i, row in enumerate(data):
        row_num = i + 1
        sku_id = row.get('SKU_ID', 'N/A')
        
        # Check required fields
        if not row.get("WEEKLY_UNITS") and row.get("WEEKLY_UNITS") != 0:
            errors.append(f"Row {row_num} ({sku_id}): Missing Weekly Units")
        if not row.get("CURRENT_FACINGS") and row.get("CURRENT_FACINGS") != 0:
            errors.append(f"Row {row_num} ({sku_id}): Missing Current Facings")
        
        # Validate integer fields
        integer_fields = {
            "WEEKLY_UNITS": "Weekly Units",
            "CURRENT_FACINGS": "Current Facings",
            "PACK_WIDTH_MM": "Pack Width"
        }
        
        for field, label in integer_fields.items():
            value = row.get(field)
            if value is not None and value != "":
                if isinstance(value, str):
                    errors.append(f"Row {row_num} ({sku_id}): {label} must be a number (not text)")
                elif not isinstance(value, int):
                    try:
                        int_val = int(value)
                        if int_val != value:
                            errors.append(f"Row {row_num} ({sku_id}): {label} must be a whole number (got {value})")
                    except (ValueError, TypeError):
                        errors.append(f"Row {row_num} ({sku_id}): {label} has invalid value: {value}")
                elif value < 0:
                    errors.append(f"Row {row_num} ({sku_id}): {label} must be positive (got {value})")
        
        # Validate float fields
        float_fields = {
            "UNIT_PRICE": "Unit Price",
            "UNIT_COST": "Unit Cost",
            "GROSS_MARGIN_PCT": "Margin %"
        }
        
        for field, label in float_fields.items():
            value = row.get(field)
            if value is not None and value != "":
                if isinstance(value, str):
                    errors.append(f"Row {row_num} ({sku_id}): {label} must be a number (not text)")
                elif not isinstance(value, (int, float)):
                    errors.append(f"Row {row_num} ({sku_id}): {label} has invalid value: {value}")
                elif value < 0:
                    errors.append(f"Row {row_num} ({sku_id}): {label} must be positive (got {value})")
        
        # Validate categorical fields
        status = row.get("STATUS")
        if status and status not in VALID_STATUSES:
            warnings.append(f"Row {row_num} ({sku_id}): Status '{status}' is not standard")
        
        category = row.get("CATEGORY")
        if category and category not in VALID_CATEGORIES:
            warnings.append(f"Row {row_num} ({sku_id}): Category '{category}' is not in standard list")
        
        # Business logic validation
        unit_price = row.get("UNIT_PRICE")
        unit_cost = row.get("UNIT_COST")
        if unit_price is not None and unit_cost is not None:
            if isinstance(unit_price, (int, float)) and isinstance(unit_cost, (int, float)):
                if unit_cost > unit_price:
                    warnings.append(f"Row {row_num} ({sku_id}): Cost (${unit_cost}) exceeds Price (${unit_price})")
    
    return {
        "errors": errors,
        "warnings": warnings,
        "duplicates": duplicates
    }


def print_results(test_name: str, results: Dict[str, List[str]]):
    """Pretty print validation results"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print('='*80)
    
    if results['duplicates']:
        print(f"\n🔴 DUPLICATE SKU IDs ({len(results['duplicates'])}):")
        for dup in results['duplicates']:
            print(f"  • {dup}")
    
    if results['errors']:
        print(f"\n🔴 CRITICAL ERRORS ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"  • {error}")
    
    if results['warnings']:
        print(f"\n🟡 WARNINGS ({len(results['warnings'])}):")
        for warning in results['warnings']:
            print(f"  • {warning}")
    
    if not results['errors'] and not results['warnings'] and not results['duplicates']:
        print("\n✅ ALL VALIDATION PASSED - Data is valid!")
    else:
        can_submit = not results['errors'] and not results['duplicates']
        status = "CAN SUBMIT (with warnings)" if can_submit else "CANNOT SUBMIT"
        print(f"\n📊 Status: {status}")


def main():
    """Run validation tests"""
    
    print("=" * 80)
    print("DASH AG GRID DATA VALIDATION TEST SUITE")
    print("=" * 80)
    
    # Test 1: Valid data
    valid_data = [
        {
            "SKU_ID": "SKU3001",
            "SKU_NAME": "Stone & Wood Pacific Ale 6pk",
            "WEEKLY_UNITS": 85,
            "CURRENT_FACINGS": 3,
            "PACK_WIDTH_MM": 180,
            "UNIT_PRICE": 24.00,
            "UNIT_COST": 14.40,
            "GROSS_MARGIN_PCT": 40.0,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(valid_data)
    print_results("Valid Data - Should Pass All Checks", results)
    
    # Test 2: String instead of integer
    string_error_data = [
        {
            "SKU_ID": "SKU3002",
            "WEEKLY_UNITS": "85",  # ❌ String, should be integer
            "CURRENT_FACINGS": 2,
            "UNIT_PRICE": 23.00,
            "UNIT_COST": 13.80,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(string_error_data)
    print_results("String Instead of Integer - Should Show Error", results)
    
    # Test 3: Float instead of integer
    float_error_data = [
        {
            "SKU_ID": "SKU3003",
            "WEEKLY_UNITS": 95,
            "CURRENT_FACINGS": 2.5,  # ❌ Float, should be integer
            "UNIT_PRICE": 22.00,
            "UNIT_COST": 13.20,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(float_error_data)
    print_results("Float Instead of Integer - Should Show Error", results)
    
    # Test 4: Negative value
    negative_error_data = [
        {
            "SKU_ID": "SKU3004",
            "WEEKLY_UNITS": -10,  # ❌ Negative
            "CURRENT_FACINGS": 2,
            "UNIT_PRICE": 20.00,
            "UNIT_COST": 12.00,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(negative_error_data)
    print_results("Negative Value - Should Show Error", results)
    
    # Test 5: Invalid category (warning only)
    invalid_category_data = [
        {
            "SKU_ID": "SKU3005",
            "WEEKLY_UNITS": 70,
            "CURRENT_FACINGS": 2,
            "UNIT_PRICE": 23.50,
            "UNIT_COST": 14.10,
            "STATUS": "pending",  # ⚠️ Not in valid list
            "CATEGORY": "Wine"     # ⚠️ Not in valid list
        }
    ]
    results = validate_sku_data(invalid_category_data)
    print_results("Invalid Category - Should Show Warning (Can Still Submit)", results)
    
    # Test 6: Cost exceeds price (warning)
    negative_margin_data = [
        {
            "SKU_ID": "SKU3006",
            "WEEKLY_UNITS": 45,
            "CURRENT_FACINGS": 2,
            "UNIT_PRICE": 20.00,
            "UNIT_COST": 25.00,  # ⚠️ Cost > Price
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(negative_margin_data)
    print_results("Cost Exceeds Price - Should Show Warning", results)
    
    # Test 7: Missing required fields
    missing_fields_data = [
        {
            "SKU_ID": "SKU3007",
            # Missing WEEKLY_UNITS
            "CURRENT_FACINGS": 2,
            "UNIT_PRICE": 22.50,
            "UNIT_COST": 13.50,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(missing_fields_data)
    print_results("Missing Required Fields - Should Show Error", results)
    
    # Test 8: Duplicate SKU IDs
    duplicate_data = [
        {
            "SKU_ID": "SKU3001",
            "WEEKLY_UNITS": 85,
            "CURRENT_FACINGS": 3,
            "UNIT_PRICE": 24.00,
            "UNIT_COST": 14.40,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        },
        {
            "SKU_ID": "SKU3001",  # ❌ Duplicate
            "WEEKLY_UNITS": 75,
            "CURRENT_FACINGS": 2,
            "UNIT_PRICE": 23.00,
            "UNIT_COST": 13.80,
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(duplicate_data)
    print_results("Duplicate SKU IDs - Should Show Error", results)
    
    # Test 9: Multiple errors combined
    multiple_errors_data = [
        {
            "SKU_ID": "SKU3008",
            "WEEKLY_UNITS": "not_a_number",  # ❌ String
            "CURRENT_FACINGS": -5,            # ❌ Negative
            "UNIT_PRICE": "$25.00",           # ❌ String with $ sign
            "UNIT_COST": 30.00,               # ⚠️ Cost > Price
            "STATUS": "unknown",              # ⚠️ Invalid status
            "CATEGORY": "Spirits"             # ⚠️ Invalid category
        }
    ]
    results = validate_sku_data(multiple_errors_data)
    print_results("Multiple Errors - Should Show Multiple Issues", results)
    
    # Test 10: Edge case - zero values (should be valid)
    zero_values_data = [
        {
            "SKU_ID": "SKU3009",
            "WEEKLY_UNITS": 0,       # ✅ Zero is valid
            "CURRENT_FACINGS": 0,    # ✅ Zero is valid
            "UNIT_PRICE": 0.0,       # ✅ Zero is valid (clearance?)
            "UNIT_COST": 0.0,        # ✅ Zero is valid
            "STATUS": "active",
            "CATEGORY": "Beer & Seltzer"
        }
    ]
    results = validate_sku_data(zero_values_data)
    print_results("Zero Values - Should Pass (Zero is Valid)", results)
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)
    print("\n📚 For full documentation, see: DATA_VALIDATION_RULES.md")
    print("🔧 Implementation files:")
    print("  • ui_app/range_optimizer/backend/components/input.py")
    print("  • mcp_app/range_optimizer/backend/components/input.py")
    print()


if __name__ == "__main__":
    main()
