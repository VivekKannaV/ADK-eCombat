"""
repositories.py — Re-export facade for the repository layer.

Import from here for backwards compatibility, or import directly from the
individual modules for clarity:

    from eCombat.src.services.product_repository       import ProductRepository
    from eCombat.src.services.order_repository         import OrderRepository
    from eCombat.src.services.session_repository       import SessionRepository
    from eCombat.src.services.session_history_service  import SessionHistoryService
"""

from eCombat.src.services.order_repository import OrderRepository
from eCombat.src.services.product_repository import ProductRepository
from eCombat.src.services.session_history_service import SessionHistoryService
from eCombat.src.services.session_repository import SessionRepository

__all__ = ["ProductRepository", "OrderRepository", "SessionRepository", "SessionHistoryService"]
