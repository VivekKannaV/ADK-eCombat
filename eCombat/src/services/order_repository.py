"""order_repository.py — Data access for the ``orders`` table."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from psycopg2.extras import DictCursor

from eCombat.src.services.utils.postgres_pool import get_connection
from eCombat.src.services.utils.row_utils import row_to_dict


class OrderRepository:
    """Read/write access to the ``orders`` table."""

    @staticmethod
    def create(
        customer_name: str,
        product_id: int,
        quantity: int,
        total_price: float,
    ) -> Dict[str, Any]:
        """Insert a new order row and return its details."""
        sql = """
            INSERT INTO orders (customer_name, product_id, quantity, total_price, status)
            VALUES (%s, %s, %s, %s, 'Pending')
            RETURNING id, status, order_date
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (customer_name, product_id, quantity, total_price))
                row = cur.fetchone()
                return row_to_dict(row)

    @staticmethod
    def get_by_id(order_id: int) -> Optional[Dict[str, Any]]:
        """Return order details joined with the product name, or ``None``."""
        sql = """
            SELECT o.id, o.customer_name, p.name AS product_name,
                   o.quantity, o.total_price, o.status, o.order_date
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.id = %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (order_id,))
                row = cur.fetchone()
                return row_to_dict(row) if row else None

    @staticmethod
    def list_by_customer(customer_name: str) -> List[Dict[str, Any]]:
        """Return all orders for a customer, newest first."""
        sql = """
            SELECT o.id, o.customer_name, p.name AS product_name,
                   o.quantity, o.total_price, o.status, o.order_date
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.customer_name ILIKE %s
            ORDER BY o.order_date DESC
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (customer_name,))
                return [row_to_dict(row) for row in cur.fetchall()]
