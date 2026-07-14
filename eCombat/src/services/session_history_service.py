"""session_history_service.py — Durable conversation-turn storage in PostgreSQL.

Each agent/user message is stored as an individual row in the
``conversation_turns`` table so that a full conversation can be replayed
from the database after the session ends.

Table schema (managed by ``scripts/init_db.sql``)::

    conversation_turns (
        id          SERIAL PRIMARY KEY,
        session_id  VARCHAR(255) NOT NULL,
        user_id     VARCHAR(255),
        role        VARCHAR(50)  NOT NULL,   -- 'user' | 'assistant' | 'tool' | 'system'
        content     TEXT         NOT NULL,
        tool_calls  JSONB,
        timestamp   TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Union

from psycopg2.extras import DictCursor

from eCombat.src.services.utils.postgres_pool import get_connection
from eCombat.src.services.utils.row_utils import row_to_dict

logger = logging.getLogger(__name__)

# Valid role values — matches the CHECK constraint in the DB.
VALID_ROLES = frozenset({"user", "assistant", "tool", "system"})


class SessionHistoryService:
    """Service for persisting and retrieving conversation turns."""

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def save_turn(
        session_id: str,
        role: str,
        content: str,
        *,
        user_id: Optional[str] = None,
        tool_calls: Optional[Union[List[Any], Dict[str, Any]]] = None,
    ) -> int:
        """Persist a single conversation turn and return the new row id.

        Parameters
        ----------
        session_id:
            Unique identifier for the conversation session.
        role:
            Message author role — one of ``'user'``, ``'assistant'``,
            ``'tool'``, or ``'system'``.
        content:
            The text content of the message.
        user_id:
            Optional identifier for the human user (may be ``None`` for
            assistant / tool / system turns).
        tool_calls:
            Optional list or dict of tool call payloads to store as JSONB.
            Will be JSON-serialised before insertion.
        """
        if role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {sorted(VALID_ROLES)}."
            )

        tool_calls_json: Optional[str] = (
            json.dumps(tool_calls) if tool_calls is not None else None
        )

        sql = """
            INSERT INTO conversation_turns
                (session_id, user_id, role, content, tool_calls)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (session_id, user_id, role, content, tool_calls_json),
                )
                row_id: int = cur.fetchone()[0]

        logger.debug(
            "Saved turn id=%d session=%s role=%s", row_id, session_id, role
        )
        return row_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_history(
        session_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return conversation turns for a session ordered oldest-first.

        Parameters
        ----------
        session_id:
            The session to retrieve.
        limit:
            Maximum number of turns to return (default 100).

        Returns
        -------
        list[dict]
            Each dict has keys: ``id``, ``session_id``, ``user_id``,
            ``role``, ``content``, ``tool_calls``, ``timestamp``.
            ``tool_calls`` is decoded back to a Python object (list/dict)
            when present.
        """
        sql = """
            SELECT id, session_id, user_id, role, content, tool_calls, timestamp
            FROM   conversation_turns
            WHERE  session_id = %s
            ORDER  BY timestamp ASC, id ASC
            LIMIT  %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(sql, (session_id, limit))
                rows = cur.fetchall()

        result = []
        for row in rows:
            d = row_to_dict(row)
            # tool_calls comes back as a Python object from psycopg2's JSONB
            # handling; no extra decoding needed.
            result.append(d)
        return result
