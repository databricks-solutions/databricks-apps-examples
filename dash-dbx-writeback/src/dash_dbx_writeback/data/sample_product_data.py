import random
from typing import List, Dict, Any, Optional, Tuple

INITIAL_DATA = [
    {
        "LAYOUT_ID": "LAY001",
        "SELL_ID": "SELL001",
        "PRODUCT_NAME": "Coles Brand Milk 2L",
        "LOYALTY_GROUP": "Core",
        "SEGMENT_1": "High Value",
        "SEGMENT_2": "Regular Shopper",
        "ORIGIN": "AU",
        "CATEGORY_NAME": "Dairy",
        "SUBCATEGORY_NAME": "Milk",
        "ITEM_CLASS_NAME": "Full Cream",
        "SUPPLIER": "Coles Dairy",
        "BRAND": "Coles",
        "PACK_SIZE": "2L",
    },
    {
        "LAYOUT_ID": "LAY002",
        "SELL_ID": "SELL002",
        "PRODUCT_NAME": "Woolworths Bread White",
        "LOYALTY_GROUP": "Core",
        "SEGMENT_1": "Regular Shopper",
        "SEGMENT_2": "Family",
        "ORIGIN": "AU",
        "CATEGORY_NAME": "Bakery",
        "SUBCATEGORY_NAME": "Bread",
        "ITEM_CLASS_NAME": "White",
        "SUPPLIER": "Woolworths Bakery",
        "BRAND": "Woolworths",
        "PACK_SIZE": "650g",
    },
    {
        "LAYOUT_ID": "LAY003",
        "SELL_ID": "SELL003",
        "PRODUCT_NAME": "Arnott's Tim Tams",
        "LOYALTY_GROUP": "Premium",
        "SEGMENT_1": "High Value",
        "SEGMENT_2": "Regular Shopper",
        "ORIGIN": "AU",
        "CATEGORY_NAME": "Confectionery",
        "SUBCATEGORY_NAME": "Biscuits",
        "ITEM_CLASS_NAME": "Chocolate",
        "SUPPLIER": "Arnott's",
        "BRAND": "Arnott's",
        "PACK_SIZE": "200g",
    },
    {
        "LAYOUT_ID": "LAY004",
        "SELL_ID": "SELL004",
        "PRODUCT_NAME": "Vegemite 380g",
        "LOYALTY_GROUP": "Core",
        "SEGMENT_1": "Family",
        "SEGMENT_2": "Regular Shopper",
        "ORIGIN": "AU",
        "CATEGORY_NAME": "Pantry",
        "SUBCATEGORY_NAME": "Spreads",
        "ITEM_CLASS_NAME": "Yeast Extract",
        "SUPPLIER": "Bega",
        "BRAND": "Vegemite",
        "PACK_SIZE": "380g",
    },
    {
        "LAYOUT_ID": "LAY005",
        "SELL_ID": "SELL005",
        "PRODUCT_NAME": "Kangaroo Steak",
        "LOYALTY_GROUP": "Premium",
        "SEGMENT_1": "Health Conscious",
        "SEGMENT_2": "High Value",
        "ORIGIN": "AU",
        "CATEGORY_NAME": "Meat",
        "SUBCATEGORY_NAME": "Game",
        "ITEM_CLASS_NAME": "Steak",
        "SUPPLIER": "Macro Meats",
        "BRAND": "Macro",
        "PACK_SIZE": "500g",
    },
    {
        "LAYOUT_ID": "LAY006",
        "SELL_ID": "SELL006",
        "PRODUCT_NAME": "Tim Tam Slam Kit",
        "LOYALTY_GROUP": "Premium",
        "SEGMENT_1": "Impulse Buyer",
        "SEGMENT_2": "High Value",
        "ORIGIN": "AU",
        "CATEGORY_NAME": "Confectionery",
        "SUBCATEGORY_NAME": "Biscuits",
        "ITEM_CLASS_NAME": "Gift Set",
        "SUPPLIER": "Arnott's",
        "BRAND": "Arnott's",
        "PACK_SIZE": "400g",
    },
]


def generate_product_data(
    num_products: int = 3,
    categories: Optional[List[str]] = None,
    brands: Optional[List[str]] = None,
    suppliers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Generate sample product data for testing and development.

    Args:
        num_products (int): Number of products to generate
        categories (list): List of possible category names
        brands (list): List of possible brand names
        suppliers (list): List of possible supplier names

    Returns:
        list: List of dictionaries containing product data
    """
    if categories is None:
        categories = ["Dairy", "Bakery", "Confectionery", "Skin Care"]
    if brands is None:
        brands = ["Coles", "Arnott's", "L'OREAL PARIS"]
    if suppliers is None:
        suppliers = ["Coles Dairy", "Arnott's", "L'Oréal"]

    products = []
    for i in range(num_products):
        product = {
            "LAYOUT_ID": f"LAY{str(i+1).zfill(3)}",
            "SELL_ID": f"SELL{str(i+1).zfill(3)}",
            "PRODUCT_NAME": f"Sample Product {i+1}",
            "LOYALTY_GROUP": random.choice(["Core", "Premium", "Value"]),
            "SEGMENT_1": random.choice(["High Value", "Regular Shopper", "Family"]),
            "SEGMENT_2": random.choice(["Budget", "Premium", "Urban"]),
            "ORIGIN": "AU",
            "CATEGORY_NAME": random.choice(categories),
            "SUBCATEGORY_NAME": f"Subcategory {i+1}",
            "ITEM_CLASS_NAME": f"Item Class {i+1}",
            "SUPPLIER": random.choice(suppliers),
            "BRAND": random.choice(brands),
            "PACK_SIZE": f"{random.randint(1, 5)}L",
        }
        products.append(product)

    return products
