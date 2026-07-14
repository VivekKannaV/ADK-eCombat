"""session_repository.py — Backward-compatible façade over SessionHistoryService.

The underlying storage was migrated to the ``conversation_turns`` table
(see ``session_history_service.py``).  This module keeps ``SessionRepository``
alive so that existing callers do not need to change their imports.

Deprecated — prefer ``SessionHistoryService`` directly for new code.
"""

from __future__ import annotations

from typing import Any, Dict, List

from eCombat.src.services.session_history_service import SessionHistoryService


class SessionRepository:
    """Thin façade kept for backward compatibility.

    ``save()`` stores the user query and agent response as two separate turns
    (``'user'`` and ``'assistant'``) in ``conversation_turns``.
    ``get_history()`` returns turns reassembled into the legacy dict shape.
    """

    @staticmethod
    def save(
        session_id: str,
        user_query: str,
        agent_response: str,
        *,
        user_id: str | None = None,
    ) -> int:
        """Persist a user/assistant exchange and return the assistant turn id."""
        SessionHistoryService.save_turn(
            session_id, "user", user_query, user_id=user_id
        )
        return SessionHistoryService.save_turn(
            session_id, "assistant", agent_response, user_id=None
        )

    @staticmethod
    def get_history(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Return paired interactions in the legacy ``{user_query, agent_response}`` shape.

        Turns are read from ``conversation_turns`` and paired sequentially so
        that each returned dict contains one user message and the assistant
        reply that followed it.
        """
        turns = SessionHistoryService.get_history(session_id, limit=limit * 2)

        paired: List[Dict[str, Any]] = []
        pending_user: Dict[str, Any] | None = None
        for turn in turns:
            if turn["role"] == "user":
                pending_user = turn
            elif turn["role"] == "assistant" and pending_user is not None:
                paired.append(
                    {
                        "id": turn["id"],
                        "session_id": turn["session_id"],
                        "user_query": pending_user["content"],
                        "agent_response": turn["content"],
                        "timestamp": turn["timestamp"],
                    }
                )
                pending_user = None
        return paired[:limit]
