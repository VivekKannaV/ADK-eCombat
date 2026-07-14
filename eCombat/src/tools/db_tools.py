"""db_tools.py — Backward-compatible re-exports.

All tool functions have been split per SRP:

  - sales_tools.py   → search_products, place_order     (SalesAgent)
  - support_tools.py → get_order_status                 (SupportAgent)
  - session_tools.py → log_session_interaction          (shared infra)

Import directly from those modules going forward.
"""

from eCombat.src.tools.sales_tools import search_products, place_order
from eCombat.src.tools.support_tools import get_order_status
from eCombat.src.tools.session_tools import log_session_interaction

__all__ = [
    "search_products",
    "place_order",
    "get_order_status",
    "log_session_interaction",
]

