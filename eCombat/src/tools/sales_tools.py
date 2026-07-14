"""sales_tools.py — Tools for the SalesAgent.

Covers the pre-purchase domain:
  - Product catalog discovery and search.
  - Order placement (checkout / purchase flow).
"""

from typing import Any, Dict, List, Optional

from google.adk.tools.tool_context import ToolContext

from eCombat.src.services.utils.postgres_pool import DatabaseError
from eCombat.src.services.order_repository import OrderRepository
from eCombat.src.services.product_repository import ProductRepository


def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    tool_context: ToolContext = None,
) -> List[Dict[str, Any]]:
    """
    Search the electronics product catalog.

    Args:
        query: Part of the product name or description to filter by.
        category: Exact category to filter by (e.g. 'Smartphones', 'Laptops',
            'Audio', 'Wearables', 'Smart Home').
        max_price: Maximum price filter.

    Returns:
        A list of matching products, each with keys: id, name, description,
        price, stock_quantity, category.
    """
    try:
        results = ProductRepository.search(query=query, category=category, max_price=max_price)
        if tool_context is not None and results and not isinstance(results, dict):
            tool_context.state["last_lookup_key"] = query or category or ""
            tool_context.state["current_product_id"] = results[0]["id"]
        return results
    except DatabaseError as exc:
        return {"error": str(exc)}


def place_order(
    customer_name: str,
    product_name: str,
    quantity: int,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """
    Place a new customer order for an electronics product.

    Args:
        customer_name: The full name of the customer placing the order.
        product_name: The exact name of the product to purchase
            (e.g., 'iPhone 15 Pro Max').
        quantity: The quantity to buy. Must be greater than 0.

    Returns:
        A dictionary with the order details or an error message if stock is
        insufficient or the product is not found.
    """
    if quantity <= 0:
        return {"error": "Quantity must be greater than 0."}

    try:
        product = ProductRepository.get_by_name(product_name)
        if not product:
            return {"error": f"Product '{product_name}' not found."}

        if product["stock_quantity"] < quantity:
            return {"error": f"Insufficient stock. Only {product['stock_quantity']} units available."}

        total_price = float(product["price"]) * quantity

        # Deduct stock then create the order inside the same logical unit;
        # each repository call uses its own pool connection and auto-commits.
        ProductRepository.deduct_stock(product["id"], quantity)
        order = OrderRepository.create(customer_name, product["id"], quantity, total_price)

        result = {
            "order_id": order["id"],
            "customer_name": customer_name,
            "product_name": product_name,
            "quantity": quantity,
            "total_price": total_price,
            "status": order["status"],
            "order_date": str(order["order_date"]),
        }
        if tool_context is not None:
            tool_context.state["current_order_id"] = order["id"]
            tool_context.state["current_customer_name"] = customer_name
            tool_context.state["current_product_id"] = product["id"]
        return result
    except DatabaseError as exc:
        return {"error": str(exc)}
