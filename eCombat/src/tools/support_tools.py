"""support_tools.py — Tools for the SupportAgent.

Covers the post-purchase domain:
  - Order status and detail lookups.
"""

from typing import Any, Dict

from google.adk.tools.tool_context import ToolContext

from eCombat.src.services.utils.postgres_pool import DatabaseError
from eCombat.src.services.order_repository import OrderRepository


def get_order_status(order_id: int, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Retrieve the status and details of an existing order.

    Args:
        order_id: The unique ID of the order.

    Returns:
        A dictionary with order information, or an error if not found.
    """
    try:
        order = OrderRepository.get_by_id(order_id)
        if not order:
            return {"error": f"Order #{order_id} not found."}
        order["order_date"] = str(order["order_date"])
        if tool_context is not None:
            tool_context.state["current_order_id"] = order_id
        return order
    except DatabaseError as exc:
        return {"error": str(exc)}
