"""session_tools.py — Session state persistence (Redis + Postgres).

Redis layer:
    Fast, TTL-based session state stored under ``session:<session_id>``.
    Used for in-flight conversation history and per-session context.

Postgres layer (``log_session_interaction``):
    Durable, queryable audit trail written to the ``conversation_turns``
    table via ``SessionHistoryService``.

All configuration (host, port, password, db) is read from
``eCombat.src.config.settings`` which in turn reads from the ``.env`` file —
nothing is hard-coded here.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import redis

from eCombat.src.services.utils.postgres_pool import DatabaseError
from eCombat.src.services.session_history_service import SessionHistoryService

from eCombat.src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


# ---------------------------------------------------------------------------
# Connection pool — created once at module import time, reused across calls.
# ---------------------------------------------------------------------------

_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD or None,
    decode_responses=True,
)


def _get_client() -> redis.Redis:
    """Return a Redis client backed by the shared connection pool."""
    return redis.Redis(connection_pool=_pool)


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

_SESSION_PREFIX = "session"
_DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def _session_key(session_id: str) -> str:
    return f"{_SESSION_PREFIX}:{session_id}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_session_interaction(
    session_id: str,
    user_query: str,
    agent_response: str,
    *,
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> Dict[str, Any]:
    """Append one interaction turn to the session history stored in Redis.

    Args:
        session_id: Unique identifier for the conversation session.
        user_query: The customer's message for this turn.
        agent_response: The agent's reply for this turn.
        ttl: Time-to-live in seconds for the session key (default: 24 h).
            Pass ``0`` to keep the key indefinitely.

    Returns:
        A status dict: ``{"status": "success", "turn": <int>}`` on success,
        or ``{"status": "error", "message": <str>}`` on failure.
    """
    client = _get_client()
    key = _session_key(session_id)
    entry = {
        "user_query": user_query,
        "agent_response": agent_response,
        "timestamp": time.time(),
    }
    try:
        # Use a pipeline for atomic append + TTL refresh
        pipe = client.pipeline()
        raw = client.get(f"{key}:history")
        history: List[Dict[str, Any]] = json.loads(raw) if raw else []
        history.append(entry)
        pipe.set(f"{key}:history", json.dumps(history))
        if ttl > 0:
            pipe.expire(f"{key}:history", ttl)
        pipe.execute()
        return {"status": "success", "turn": len(history)}
    except redis.RedisError as exc:
        return {"status": "error", "message": str(exc)}


def get_session_history(
    session_id: str,
) -> Dict[str, Any]:
    """Retrieve the full conversation history for a session.

    Args:
        session_id: Unique identifier for the conversation session.

    Returns:
        ``{"status": "success", "history": [<turn>, ...]}`` where each turn
        has keys ``user_query``, ``agent_response``, and ``timestamp``
        (Unix float).  Returns an empty list when the session has never been
        seen or has expired.  Returns ``{"status": "error", ...}`` on Redis
        failures.
    """
    client = _get_client()
    key = _session_key(session_id)
    try:
        raw = client.get(f"{key}:history")
        history: List[Dict[str, Any]] = json.loads(raw) if raw else []
        return {"status": "success", "history": history}
    except redis.RedisError as exc:
        return {"status": "error", "message": str(exc)}


def set_session_context(
    session_id: str,
    context: Dict[str, Any],
    *,
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> Dict[str, Any]:
    """Persist arbitrary key-value context for a session (e.g. cart, preferences).

    Values must be JSON-serialisable.  The entire ``context`` dict overwrites
    any previous context stored for this session.

    Args:
        session_id: Unique identifier for the conversation session.
        context: Mapping of context keys to JSON-serialisable values.
        ttl: Time-to-live in seconds (default: 24 h).

    Returns:
        ``{"status": "success"}`` or ``{"status": "error", "message": ...}``.
    """
    client = _get_client()
    key = _session_key(session_id)
    try:
        pipe = client.pipeline()
        pipe.set(f"{key}:context", json.dumps(context))
        if ttl > 0:
            pipe.expire(f"{key}:context", ttl)
        pipe.execute()
        return {"status": "success"}
    except (redis.RedisError, TypeError) as exc:
        return {"status": "error", "message": str(exc)}


def get_session_context(
    session_id: str,
) -> Dict[str, Any]:
    """Retrieve the context dict previously saved for a session.

    Args:
        session_id: Unique identifier for the conversation session.

    Returns:
        ``{"status": "success", "context": {...}}`` or an empty dict when
        the session has no stored context.
    """
    client = _get_client()
    key = _session_key(session_id)
    try:
        raw = client.get(f"{key}:context")
        context: Dict[str, Any] = json.loads(raw) if raw else {}
        return {"status": "success", "context": context}
    except redis.RedisError as exc:
        return {"status": "error", "message": str(exc)}


def delete_session(session_id: str) -> Dict[str, Any]:
    """Remove all Redis keys associated with a session.

    Args:
        session_id: Unique identifier for the conversation session.

    Returns:
        ``{"status": "success", "deleted": <int>}`` with the count of keys
        removed, or ``{"status": "error", "message": ...}`` on failure.
    """
    client = _get_client()
    key = _session_key(session_id)
    try:
        deleted = client.delete(f"{key}:history", f"{key}:context")
        return {"status": "success", "deleted": deleted}
    except redis.RedisError as exc:
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Durable audit log (Redis + Postgres)
# ---------------------------------------------------------------------------

def log_session_interaction(
    session_id: str,
    user_query: str,
    agent_response: str,
    *,
    user_id: Optional[str] = None,
    tool_calls: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Log a user/agent turn to both Redis (fast, TTL-based) and Postgres
    (durable, queryable).

    Args:
        session_id: Unique session identifier.
        user_query: The customer's message.
        agent_response: The agent's final answer.
        user_id: Optional user identifier to attach to the user turn.
        tool_calls: Optional list of tool call payloads for the assistant turn.

    Returns:
        A status message indicating success or failure.
    """
    # --- 1. Fast session state → Redis ---
    redis_result = save_session_interaction(session_id, user_query, agent_response)
    if redis_result["status"] != "success":
        return {"status": "Error", "message": f"Redis: {redis_result['message']}"}

    # --- 2. Durable audit log → Postgres (one turn per role) ---
    try:
        SessionHistoryService.save_turn(
            session_id, "user", user_query, user_id=user_id
        )
        SessionHistoryService.save_turn(
            session_id, "assistant", agent_response, user_id=None, tool_calls=tool_calls
        )
        return {"status": "Success", "message": "Interaction logged.", "turn": redis_result["turn"]}
    except DatabaseError as exc:
        return {"status": "Error", "message": str(exc)}


def ping_redis() -> bool:
    """Return ``True`` if Redis is reachable, ``False`` otherwise.

    Useful for health-check endpoints or startup validation.
    """
    try:
        return _get_client().ping()
    except redis.RedisError:
        return False
