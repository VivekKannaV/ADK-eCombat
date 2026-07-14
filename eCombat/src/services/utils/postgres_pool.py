"""
postgres_pool.py — Reusable PostgreSQL connection pool for the eCombat application.

Usage (context manager — preferred):
    from eCombat.src.services.utils.postgres_pool import get_connection

    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT 1")

The pool is initialised lazily on first use and shared across all callers
(tools, services, repositories) in the same process.  Connections are
returned to the pool automatically when the ``with`` block exits, even if
an exception is raised.

Configuration is read from ``eCombat.src.config.settings`` (which loads the
.env file).  No credentials are hard-coded here.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import DictCursor  # re-exported for convenience

from eCombat.src.config.settings import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class DatabaseError(Exception):
    """Raised when a database operation fails.

    Wraps the underlying ``psycopg2`` exception so callers don't need to
    import psycopg2 directly to handle DB errors.
    """


# ---------------------------------------------------------------------------
# Connection pool — created lazily; a single instance is reused per process.
# ---------------------------------------------------------------------------

_MIN_CONNECTIONS = 1
_MAX_CONNECTIONS = 10

_pool: pg_pool.ThreadedConnectionPool | None = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    """Return the shared connection pool, creating it on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        try:
            _pool = pg_pool.ThreadedConnectionPool(
                minconn=_MIN_CONNECTIONS,
                maxconn=_MAX_CONNECTIONS,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
            )
            logger.info(
                "PostgreSQL connection pool created (%s:%s/%s, pool size %d–%d)",
                POSTGRES_HOST,
                POSTGRES_PORT,
                POSTGRES_DB,
                _MIN_CONNECTIONS,
                _MAX_CONNECTIONS,
            )
        except psycopg2.OperationalError as exc:
            raise DatabaseError(
                f"Could not connect to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}: {exc}"
            ) from exc
    return _pool


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a connection from the pool and return it when done.

    Automatically commits on clean exit and rolls back on any exception,
    then returns the connection to the pool in both cases.

    Example::

        from psycopg2.extras import DictCursor
        from eCombat.src.services.utils.postgres_pool import get_connection

        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT id, name FROM products LIMIT 5")
                rows = cur.fetchall()
    """
    pool = _get_pool()
    conn = None
    try:
        conn = pool.getconn()
        yield conn
        conn.commit()
    except psycopg2.Error as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise DatabaseError(f"Database operation failed: {exc}") from exc
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            pool.putconn(conn)


def close_pool() -> None:
    """Close all connections in the pool.

    Call this during application shutdown.  After calling this, the next
    call to :func:`get_connection` will create a fresh pool.
    """
    global _pool  # noqa: PLW0603
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("PostgreSQL connection pool closed.")


def health_check() -> bool:
    """Return ``True`` if the database is reachable, ``False`` otherwise.

    Suitable for liveness/readiness probes.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except DatabaseError:
        return False
