"""_utils.py — Shared helpers for the repository layer."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict


def row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert a psycopg2 DictRow to a plain dict, coercing Decimal → float."""
    d = dict(row)
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}
