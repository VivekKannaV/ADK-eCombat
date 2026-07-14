"""logging_agent.py — transparent logging wrapper for ADK Agent instances.

Production conventions followed:
  - This module NEVER configures log handlers or levels.
    Handler/formatter/level setup belongs in the application entry-point
    (e.g. main.py, gunicorn config, or a logging.config.dictConfig call).
  - Input/output payloads are logged at DEBUG so they are silent in production
    by default but visible when the log level is lowered for debugging.
  - Lifecycle events (start, finish, error) are logged at INFO / ERROR.
  - Every invocation gets a short UUID so you can correlate log lines for
    a single call even when multiple agents run concurrently.
  - Latency (wall-clock seconds) is recorded on every finish/error line.

Usage example in an application entry-point
-------------------------------------------
    import logging, logging.config

    logging.config.dictConfig({
        "version": 1,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            },
            "plain": {
                "format": "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "plain",   # swap to "json" in production
            },
        },
        "root": {"level": "INFO", "handlers": ["console"]},
        # Lower just the agent loggers to DEBUG when you want payload details:
        # "loggers": {"eCombat.agents": {"level": "DEBUG"}},
    })
"""

import logging
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from pydantic import PrivateAttr

from eCombat.src.tools.session_tools import log_session_interaction


def _truncate(value: Any, max_chars: int) -> str:
    """Return a string representation of *value* capped at *max_chars* chars."""
    text = repr(value)
    if len(text) > max_chars:
        return text[:max_chars] + f"… [truncated, {len(text)} chars total]"
    return text


class LoggingAgent(BaseAgent):
    """BaseAgent subclass that wraps another agent with structured logging.

    Parameters
    ----------
    agent:
        Any ADK BaseAgent instance to wrap.
    max_output_chars:
        How many characters of the serialised output to include in DEBUG
        log lines.  Default: 500.
    log_inputs:
        When *True* (default) the user query is logged at DEBUG level.
        Set to *False* when inputs may contain PII.
    persist_interactions:
        When *True* (default) each completed invocation is persisted via
        log_session_interaction.
    """

    # Pydantic fields
    wrapped_agent: BaseAgent
    max_output_chars: int = 500
    log_inputs: bool = True
    persist_interactions: bool = True

    # Private (non-pydantic) attribute
    _logger: logging.Logger = PrivateAttr()

    def __init__(
        self,
        agent: BaseAgent,
        *,
        max_output_chars: int = 500,
        log_inputs: bool = True,
        persist_interactions: bool = True,
    ) -> None:
        super().__init__(
            name=agent.name,
            description=getattr(agent, "description", ""),
            wrapped_agent=agent,
            max_output_chars=max_output_chars,
            log_inputs=log_inputs,
            persist_interactions=persist_interactions,
        )

    def model_post_init(self, __context: Any) -> None:
        self._logger = logging.getLogger(f"eCombat.agents.{self.name}")

    # ------------------------------------------------------------------
    # Session persistence helper
    # ------------------------------------------------------------------

    def _persist(
        self,
        session_id: Optional[str],
        user_query: Optional[str],
        agent_response: str,
    ) -> None:
        """Fire-and-forget call to log_session_interaction; never raises."""
        if not self.persist_interactions or not session_id or not user_query:
            return
        try:
            log_result = log_session_interaction(
                session_id=session_id,
                user_query=user_query,
                agent_response=agent_response,
            )
            if log_result.get("status") != "Success":
                self._logger.warning(
                    "agent=%s | SESSION_LOG failed: %s",
                    self.name, log_result.get("message"),
                )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "agent=%s | SESSION_LOG exception: %s: %s",
                self.name, type(exc).__name__, exc,
            )

    # ------------------------------------------------------------------
    # ADK core invocation — this is what the runner calls
    # ------------------------------------------------------------------

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        call_id = uuid.uuid4().hex[:8]
        t0 = time.perf_counter()

        # Extract session context for logging / persistence
        session_id: Optional[str] = getattr(getattr(ctx, "session", None), "id", None)
        user_query: Optional[str] = None
        try:
            user_query = ctx.user_content.parts[0].text  # type: ignore[union-attr]
        except (AttributeError, IndexError, TypeError):
            pass

        self._logger.info("[%s] agent=%s | START", call_id, self.name)
        if self.log_inputs and user_query:
            self._logger.debug(
                "[%s] agent=%s | INPUT query=%s",
                call_id, self.name, _truncate(user_query, self.max_output_chars),
            )

        # The LLM flow reads ctx.agent to access tools/canonical_model.
        # Swap it to the wrapped LlmAgent for the duration of the call.
        original_agent = ctx.agent
        ctx.agent = self.wrapped_agent

        collected_events: list[Event] = []
        try:
            async for event in self.wrapped_agent._run_async_impl(ctx):
                collected_events.append(event)
                yield event

            elapsed = time.perf_counter() - t0
            self._logger.info(
                "[%s] agent=%s | FINISH latency=%.3fs events=%d",
                call_id, self.name, elapsed, len(collected_events),
            )
            self._persist(session_id, user_query, _truncate(collected_events, self.max_output_chars))

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            self._logger.error(
                "[%s] agent=%s | ERROR latency=%.3fs error=%s: %s",
                call_id, self.name, elapsed,
                type(exc).__name__, exc,
                exc_info=True,
            )
            raise
        finally:
            ctx.agent = original_agent
