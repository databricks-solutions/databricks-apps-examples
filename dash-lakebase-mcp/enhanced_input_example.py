"""
Enhanced Column Definitions with AG Grid Cell Editors
This shows how to upgrade the existing COLUMN_DEFS with built-in validation.

To implement:
1. Replace COLUMN_DEFS in ui_app/range_optimizer/backend/components/input.py
2. Test each editable field
3. Keep existing callback validation as secondary check
"""

# Enhanced column definitions with AG Grid cell editors
COLUMN_DEFS_ENHANCED = [
    {
        "field": "SKU_ID", 
        "headerName": "SKU ID", 
        "filter": "agTextColumnFilter", 
        "pinned": "left", 
        "width": 100,
        "editable": False  # Primary key - not editable
    },
    {
        "field": "SKU_NAME", 
        "headerName": "Product Name", 
        "filter": "agTextColumnFilter", 
        "width": 220,
        "editable": False
    },
    {
        "field": "BRAND", 
        "headerName": "Brand", 
        "filter": "agTextColumnFilter", 
        "width": 120,
        "editable": False
    },
    {
        "field": "SEGMENT", 
        "headerName": "Segment", 
        "filter": "agTextColumnFilter", 
        "width": 120,
        "editable": False
    },
    {
        "field": "PACK_SIZE", 
        "headerName": "Pack Size", 
        "filter": "agTextColumnFilter", 
        "width": 100,
        "editable": False
    },
    {
        "field": "PACK_WIDTH_MM", 
        "headerName": "Width (mm)", 
        "filter": "agNumberColumnFilter", 
        "type": "numericColumn", 
        "width": 110,
        "editable": False  # Usually not editable, but can be if needed
    },
    
    # ============================================================================
    # EDITABLE FIELD 1: WEEKLY_UNITS (Integer with validation)
    # ============================================================================
    {
        "field": "WEEKLY_UNITS",
        "headerName": "Weekly Units",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 120,
        "editable": True,
        "cellEditor": "agNumberCellEditor",
        "cellEditorParams": {
            "precision": 0,  # Integer only (no decimals)
            "min": 0,        # Must be >= 0
            "max": 99999,    # Reasonable upper limit
            "getValidationErrors": {
                "function": """
                function(params) {
                    const value = params.value;
                    if (value === null || value === undefined || value === '') {
                        return ['Weekly Units is required'];
                    }
                    if (!Number.isInteger(value)) {
                        return ['Must be a whole number (e.g., 50, not 50.5)'];
                    }
                    if (value < 0) {
                        return ['Must be positive or zero'];
                    }
                    return null;
                }
                """
            }
        },
        "valueParser": {
            "function": """
            function(params) {
                const value = params.newValue;
                if (value === null || value === undefined || value === '') {
                    return null;
                }
                const parsed = parseInt(value, 10);
                return isNaN(parsed) ? null : parsed;
            }
            """
        },
        "cellStyle": {
            "styleConditions": [
                {
                    "condition": "params.value === null || params.value === undefined || params.value === ''",
                    "style": {"backgroundColor": "#ffcccc"},
                },
                {"condition": "true", "style": {"backgroundColor": "#e6f3ff"}},
            ]
        }
    },
    
    # ============================================================================
    # EDITABLE FIELD 2: UNIT_PRICE (Float with 2 decimals)
    # ============================================================================
    {
        "field": "UNIT_PRICE",
        "headerName": "Price ($)",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 100,
        "editable": True,
        "cellEditor": "agNumberCellEditor",
        "cellEditorParams": {
            "precision": 2,  # 2 decimal places for currency
            "min": 0,        # Must be positive
            "step": 0.01,    # Increment by cents
        },
        "valueParser": {
            "function": """
            function(params) {
                const value = params.newValue;
                if (value === null || value === undefined || value === '') {
                    return null;
                }
                const parsed = parseFloat(value);
                return isNaN(parsed) ? null : Math.round(parsed * 100) / 100;
            }
            """
        },
        "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
        "cellStyle": {
            "styleConditions": [
                {
                    "condition": "params.value === null || params.value === undefined || params.value === ''",
                    "style": {"backgroundColor": "#ffcccc"},
                },
                {"condition": "true", "style": {"backgroundColor": "#e6f3ff"}},
            ]
        }
    },
    
    # ============================================================================
    # EDITABLE FIELD 3: UNIT_COST (Float with 2 decimals)
    # ============================================================================
    {
        "field": "UNIT_COST",
        "headerName": "Cost ($)",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 100,
        "editable": True,
        "cellEditor": "agNumberCellEditor",
        "cellEditorParams": {
            "precision": 2,
            "min": 0,
            "step": 0.01,
        },
        "valueParser": {
            "function": """
            function(params) {
                const value = params.newValue;
                if (value === null || value === undefined || value === '') {
                    return null;
                }
                const parsed = parseFloat(value);
                return isNaN(parsed) ? null : Math.round(parsed * 100) / 100;
            }
            """
        },
        "valueFormatter": {"function": "d3.format(',.2f')(params.value)"},
        "cellStyle": {
            "styleConditions": [
                {
                    "condition": "params.value === null || params.value === undefined || params.value === ''",
                    "style": {"backgroundColor": "#ffcccc"},
                },
                {"condition": "true", "style": {"backgroundColor": "#e6f3ff"}},
            ]
        }
    },
    
    {
        "field": "GROSS_MARGIN_PCT",
        "headerName": "Margin %",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 100,
        "editable": False,  # Usually calculated, not directly editable
        "valueFormatter": {"function": "d3.format('.1f')(params.value) + '%'"},
    },
    
    # ============================================================================
    # EDITABLE FIELD 4: CURRENT_FACINGS (Integer with validation)
    # ============================================================================
    {
        "field": "CURRENT_FACINGS",
        "headerName": "Current Facings",
        "filter": "agNumberColumnFilter",
        "type": "numericColumn",
        "width": 130,
        "editable": True,
        "cellEditor": "agNumberCellEditor",
        "cellEditorParams": {
            "precision": 0,  # Integer only
            "min": 0,        # Must be >= 0
            "max": 50,       # Reasonable max for shelf facings
            "getValidationErrors": {
                "function": """
                function(params) {
                    const value = params.value;
                    if (value === null || value === undefined || value === '') {
                        return ['Current Facings is required'];
                    }
                    if (!Number.isInteger(value)) {
                        return ['Must be a whole number (e.g., 3, not 3.5)'];
                    }
                    if (value < 0) {
                        return ['Must be positive or zero'];
                    }
                    if (value > 50) {
                        return ['Value seems too high - typical max is 50'];
                    }
                    return null;
                }
                """
            }
        },
        "valueParser": {
            "function": """
            function(params) {
                const value = params.newValue;
                if (value === null || value === undefined || value === '') {
                    return null;
                }
                const parsed = parseInt(value, 10);
                return isNaN(parsed) ? null : parsed;
            }
            """
        },
        "cellStyle": {
            "styleConditions": [
                {
                    "condition": "params.value === null || params.value === undefined || params.value === ''",
                    "style": {"backgroundColor": "#ffcccc"},
                },
                {"condition": "true", "style": {"backgroundColor": "#e6f3ff"}},
            ]
        }
    },
    
    {
        "field": "IS_PRIVATE_LABEL",
        "headerName": "Private Label",
        "filter": "agTextColumnFilter",
        "width": 120,
        "editable": False,
        "cellRenderer": "agCheckboxCellRenderer",
    },
    
    # ============================================================================
    # EDITABLE FIELD 5: IS_MUST_STOCK (Boolean dropdown)
    # ============================================================================
    {
        "field": "IS_MUST_STOCK",
        "headerName": "Must Stock",
        "filter": "agTextColumnFilter",
        "width": 110,
        "editable": True,
        "cellEditor": "agSelectCellEditor",
        "cellEditorParams": {
            "values": [True, False]  # Only these values allowed
        },
        "cellRenderer": "agCheckboxCellRenderer",
        "cellStyle": {
            "styleConditions": [
                {
                    "condition": "params.value === true",
                    "style": {"backgroundColor": "#fff7e6"}  # Highlight must-stock items
                },
                {"condition": "true", "style": {"backgroundColor": "#e6f3ff"}},
            ]
        }
    },
    
    # ============================================================================
    # STATUS (Dropdown with predefined values)
    # ============================================================================
    {
        "field": "STATUS", 
        "headerName": "Status", 
        "filter": "agTextColumnFilter", 
        "width": 100,
        "editable": True,
        "cellEditor": "agSelectCellEditor",
        "cellEditorParams": {
            "values": ["active", "new", "discontinued"]  # Only these options
        },
        "cellStyle": {
            "styleConditions": [
                {
                    "condition": "params.value === 'new'",
                    "style": {"backgroundColor": "#e6f7ff", "color": "#1890ff", "fontWeight": "600"}
                },
                {
                    "condition": "params.value === 'discontinued'",
                    "style": {"backgroundColor": "#fff1f0", "color": "#cf1322", "fontWeight": "600"}
                },
                {
                    "condition": "params.value === 'active'",
                    "style": {"backgroundColor": "#f6ffed", "color": "#52c41a"}
                },
            ]
        }
    },
]


# Enhanced grid configuration with strict validation mode
def create_enhanced_grid():
    """
    Create AG Grid with enhanced validation features.
    
    Key features:
    - invalidEditValueMode: "block" - prevents closing editor until valid
    - stopEditingWhenCellsLoseFocus: False - keeps editor open if invalid
    - Built-in cell editors enforce types at input level
    """
    import dash_ag_grid as dag
    
    grid = dag.AgGrid(
        id="ag-grid-table",
        rowData=[],
        columnDefs=COLUMN_DEFS_ENHANCED,
        columnSize="autoSize",
        className="ag-theme-quartz",
        dashGridOptions={
            "undoRedoCellEditing": True,
            "undoRedoCellEditingLimit": 20,
            "rowDragManaged": True,
            "rowDragEntireRow": True,
            "rowSelection": "multiple",
            
            # ⭐ KEY VALIDATION SETTINGS ⭐
            "invalidEditValueMode": "block",  # Don't allow invalid values
            "stopEditingWhenCellsLoseFocus": False,  # Keep editor open if invalid
        },
        defaultColDef={
            "editable": False,  # Default to non-editable
            "cellDataType": False,
            "sortable": True,
            "filter": True,
            "floatingFilter": True,
            "resizable": True,
            "minWidth": 100,
        },
        csvExportParams={
            "fileName": "range_optimizer_skus.csv",
            "columnKeys": [col["field"] for col in COLUMN_DEFS_ENHANCED],
            "skipColumnGroupHeaders": True,
        },
        rowClassRules={"ag-row-hover": "true"},
        style={"--ag-row-hover-color": "#f5f5f5"},
    )
    
    return grid


# Example usage comparison
def demo_validation():
    """Demonstrates the difference between basic and enhanced validation"""
    
    print("=" * 80)
    print("ENHANCED VALIDATION DEMO")
    print("=" * 80)
    
    print("\n📊 COLUMN CONFIGURATION COMPARISON:\n")
    
    print("BEFORE (Basic editable):")
    print("""
    {
        "field": "WEEKLY_UNITS",
        "editable": True,  # ❌ Accepts any input (strings, floats, etc.)
    }
    """)
    
    print("\nAFTER (Enhanced with cell editor):")
    print("""
    {
        "field": "WEEKLY_UNITS",
        "editable": True,
        "cellEditor": "agNumberCellEditor",  # ✅ Only accepts numbers
        "cellEditorParams": {
            "precision": 0,  # ✅ Integers only
            "min": 0,        # ✅ Positive only
            "getValidationErrors": {  # ✅ Custom error messages
                "function": "..."
            }
        },
        "valueParser": {  # ✅ Converts pasted strings to numbers
            "function": "..."
        }
    }
    """)
    
    print("\n" + "=" * 80)
    print("USER EXPERIENCE COMPARISON")
    print("=" * 80)
    
    scenarios = [
        ("User types 'abc' in WEEKLY_UNITS", 
         "❌ Saved as string, error shown later",
         "✅ Rejected immediately, error shown in cell"),
        
        ("User types '50.5' in CURRENT_FACINGS",
         "❌ Saved as float, error shown later", 
         "✅ Rejected (integers only), error shown in cell"),
        
        ("User pastes '  100  ' (with spaces)",
         "❌ Saved as string with spaces",
         "✅ Parsed to integer 100 automatically"),
        
        ("User enters negative number",
         "❌ Saved, warning shown later",
         "✅ Rejected by min: 0 constraint"),
        
        ("User tries to enter invalid status",
         "⚠️ Allowed, warning shown later",
         "✅ Only dropdown options available"),
    ]
    
    print("\n| Scenario | Before (Basic) | After (Enhanced) |")
    print("|----------|----------------|------------------|")
    for scenario, before, after in scenarios:
        print(f"| {scenario} | {before} | {after} |")
    
    print("\n" + "=" * 80)
    print("IMPLEMENTATION STEPS")
    print("=" * 80)
    print("""
    1. Copy COLUMN_DEFS_ENHANCED to input.py (replaces COLUMN_DEFS)
    2. Update grid creation to use enhanced dashGridOptions
    3. Test each editable field:
       - Try typing invalid values
       - Try pasting values
       - Try using arrow keys to increment/decrement
    4. Keep existing callback validation as backup
    
    Files to update:
    • ui_app/range_optimizer/backend/components/input.py
    • mcp_app/range_optimizer/backend/components/input.py (similar changes)
    """)


if __name__ == "__main__":
    demo_validation()
    
    print("\n✨ See ENHANCED_GRID_VALIDATION.md for full documentation")
    print("📝 See enhanced_input_example.py for complete implementation\n")
