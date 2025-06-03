import pytest
from dash import html
from excel_like_dash.components.input import get_null_description, render_input_grid
from excel_like_dash.data.sample_product_data import (
    generate_product_data,
)


def test_generate_product_data_default(custom_data):

    # Check basic structure
    assert isinstance(custom_data, list)
    assert len(custom_data) == 3  # Default number of products

    # Check first product structure
    product = custom_data[0]
    assert "LAYOUT_ID" in product
    assert "SELL_ID" in product
    assert "PRODUCT_NAME" in product
    assert "STORE_COUNT" in product
    assert isinstance(product["STORE_COUNT"], int)
    assert 800 <= product["STORE_COUNT"] <= 1000  # Default range


def test_generate_product_data_custom():
    """Test generating product data with custom parameters"""
    categories = ["Dairy", "Bakery"]
    brands = ["Coles", "Woolworths"]
    suppliers = ["Coles Dairy", "Woolworths Bakery"]
    store_range = (500, 600)

    data = generate_product_data(
        num_products=2,
        categories=categories,
        brands=brands,
        suppliers=suppliers,
        store_count_range=store_range,
    )

    assert len(data) == 2
    for product in data:
        assert product["CATEGORY_NAME"] in categories
        assert product["BRAND"] in brands
        assert product["SUPPLIER"] in suppliers
        assert store_range[0] <= product["STORE_COUNT"] <= store_range[1]


def test_get_sample_data(custom_data):
    """Test the sample data structure and content"""
    assert isinstance(custom_data, list)
    assert len(custom_data) == 3

    # Check first product (Coles Milk)
    milk = custom_data[0]
    assert milk["LAYOUT_ID"] == "LAY001"
    assert milk["PRODUCT_NAME"] == "Coles Brand Milk 2L"
    assert milk["CATEGORY_NAME"] == "Dairy"
    assert milk["BRAND"] == "Coles"
    assert milk["STORE_COUNT"] == 850

    # Check second product (Woolworths Bread)
    bread = custom_data[1]
    assert bread["LAYOUT_ID"] == "LAY002"
    assert bread["PRODUCT_NAME"] == "Woolworths Bread White"
    assert bread["CATEGORY_NAME"] == "Bakery"
    assert bread["BRAND"] == "Woolworths"
    assert bread["STORE_COUNT"] == 950


def test_get_null_description_no_issues():
    """Test null description with complete data"""
    result = get_null_description(custom_data)
    assert result is None


def test_get_null_description_with_issues(custom_data):
    """Test null description with missing required fields"""
    # Remove some required fields
    custom_data[0]["LOYALTY_GROUP"] = None
    custom_data[0]["SEGMENT_1"] = None
    custom_data[1]["CB"] = None

    result = get_null_description(custom_data)
    assert isinstance(result, html.Div)
    assert "Some required fields are missing" in str(result)
    assert "Row 1" in str(result)
    assert "LOYALTY_GROUP" in str(result)
    assert "SEGMENT_1" in str(result)
    assert "CB" in str(result)


def test_get_column_definitions():
    """Test column definitions structure and content"""
    columns = get_column_definitions()

    assert isinstance(columns, list)
    assert len(columns) > 0

    # Check some key columns
    layout_col = next(col for col in columns if col["field"] == "LAYOUT_ID")
    assert layout_col["headerName"] == "Layout ID"
    assert layout_col["filter"] == "agTextColumnFilter"

    # Check editable columns
    loyalty_col = next(col for col in columns if col["field"] == "LOYALTY_GROUP")
    assert loyalty_col["editable"] is True
    assert "cellStyle" in loyalty_col

    # Check non-editable columns
    store_col = next(col for col in columns if col["field"] == "STORE_COUNT")
    assert store_col["filter"] == "agNumberColumnFilter"
    assert "editable" not in store_col


def test_editable_fields_alignment(custom_data):
    """Test that editable fields in column definitions match the required fields in get_null_description"""
    editable_fields = [
        "LOYALTY_GROUP",
        "SEGMENT_1",
        "SEGMENT_2",
        "SEGMENT_3",
        "SEGMENT_4",
        "SEGMENT_5",
        "SEGMENT_6",
        "SEGMENT_7",
        "SEGMENT_8",
        "CB",
        "KVI",
        "EDV",
        "CAT",
        "DD",
        "END",
    ]

    # Get column definitions
    columns = get_column_definitions()

    # Check that all editable fields are marked as editable in column definitions
    for field in editable_fields:
        col = next(col for col in columns if col["field"] == field)
        assert col["editable"] is True, f"Field {field} should be editable"

        # Check for cellStyle for LOYALTY_GROUP and SEGMENT_1-8
        if field in ["LOYALTY_GROUP"] + [f"SEGMENT_{i}" for i in range(1, 9)]:
            assert "cellStyle" in col, f"Field {field} should have cellStyle"

    # Check that no other fields are marked as editable
    editable_columns = [col["field"] for col in columns if col.get("editable", False)]
    assert set(editable_columns) == set(
        editable_fields
    ), "Editable columns should match editable fields"


def test_render_input_grid_default():
    """Test rendering input grid with default data"""
    grid = render_input_grid()
    assert isinstance(grid, html.Div)

    # Check that all required components are present
    assert "grid-data-store" in str(grid)
    assert "ag-grid-table" in str(grid)
    assert "null-description-box" in str(grid)
    assert "csv-button" in str(grid)
    assert "submit-button" in str(grid)


def test_render_input_grid_custom_data(custom_data):
    """Test rendering input grid with custom data"""
    grid = render_input_grid()

    assert isinstance(grid, html.Div)
    assert "grid-data-store" in str(grid)
    assert "ag-grid-table" in str(grid)
