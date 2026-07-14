"""product_repository.py — Data access for the ``products`` table."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from psycopg2.extras import DictCursor

from eCombat.src.services.utils.postgres_pool import DatabaseError, get_connection
from eCombat.src.services.utils.row_utils import row_to_dict


class ProductRepository:
    """Read/write access to the ``products`` table."""

    @staticmethod
    def search(
        query: Optional[str] = None,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Return products matching the given filters, ordered by price ASC."""
        sql = (
            "SELECT id, name, description, price, stock_quantity, category "
            "FROM products WHERE 1=1"
        )
        params: list = []

        if query:
            sql += " AND (name ILIKE %s OR description ILIKE %s)"
            params.extend([f"%{query}%", f"%{query}%"])
        if category:
            sql += " AND category = %s"
            params.append(category)
        if max_price is not None:
            sql += " AND price <= %s"
            params.append(max_price)

        sql += " ORDER BY price ASC"

        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, params)
                return [row_to_dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_by_name(name: str) -> Optional[Dict[str, Any]]:
        """Return the product with the given exact name, or ``None``."""
        sql = "SELECT id, name, price, stock_quantity FROM products WHERE name = %s"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (name,))
                row = cur.fetchone()
                return row_to_dict(row) if row else None

    @staticmethod
    def deduct_stock(product_id: int, quantity: int) -> None:
        """Reduce ``stock_quantity`` by *quantity* for the given product.

        Raises :class:`~eCombat.src.services.postgres_pool.DatabaseError` if the row
        cannot be updated (insufficient stock or product not found).
        """
        sql = (
            "UPDATE products SET stock_quantity = stock_quantity - %s "
            "WHERE id = %s AND stock_quantity >= %s"
        )
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (quantity, product_id, quantity))
                if cur.rowcount == 0:
                    raise DatabaseError(
                        f"Could not deduct {quantity} units from product {product_id} "
                        "(insufficient stock or product not found)."
                    )
