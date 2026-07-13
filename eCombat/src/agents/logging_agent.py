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

import inspect
import logging
import time
import uuid
from typing import Any

# Module-level logger used only for warnings about misconfigured wrappers.
_module_log = logging.getLogger(__name__)


def _truncate(value: Any, max_chars: int) -> str:
    """Return a string representation of *value* capped at *max_chars* chars."""
    text = repr(value)
    if len(text) > max_chars:
        return text[:max_chars] + f"… [truncated, {len(text)} chars total]"
    return text


class LoggingAgent:
    """Transparent proxy around an ADK Agent that emits structured log lines.

    Parameters
    ----------
    agent:
        Any ADK Agent instance (or compatible object).
    max_output_chars:
        How many characters of the serialised output to include in the DEBUG
        log line.  Increase for debugging, keep low (≤500) in production to
        avoid flooding your log sink.  Default: 500.
    log_inputs:
        When *True* (default) the caller args/kwargs are logged at DEBUG level.
        Set to *False* when inputs may contain PII and your pipeline does not
        have a redaction layer.
    """

    def __init__(
        self,
        agent: Any,
        *,
        max_output_chars: int = 500,
        log_inputs: bool = True,
    ) -> None:
        self._agent = agent
        self._max_output_chars = max_output_chars
        self._log_inputs = log_inputs

        agent_name = getattr(agent, "name", agent.__class__.__name__)
        # Use the standard logger hierarchy — no handlers attached here.
        self.logger = logging.getLogger(f"eCombat.agents.{agent_name}")

    # ------------------------------------------------------------------
    # Transparent attribute proxy
    # ------------------------------------------------------------------

    def __getattr__(self, item: str) -> Any:
        # Called only when the attribute is NOT found on LoggingAgent itself,
        # so internal attributes (_agent, logger, etc.) are never intercepted.
        return getattr(self._agent, item)

    # ------------------------------------------------------------------
    # Callable proxy with logging
    # ------------------------------------------------------------------

    def _find_callable(self) -> Any:
        """Return the best callable entrypoint on the wrapped agent."""
        if callable(self._agent):
            return self._agent
        for method in ("run", "handle", "process", "respond"):
            attr = getattr(self._agent, method, None)
            if callable(attr):
                return attr
        return None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        agent_name = getattr(self._agent, "name", self._agent.__class__.__name__)
        call_id = uuid.uuid4().hex[:8]   # short 8-char ID — easy to grep
        target = self._find_callable()

        if target is None:
            msg = f"No callable entrypoint found on agent '{agent_name}'"
            _module_log.error(msg)
            raise RuntimeError(msg)

        # --- log invocation start ---
        self.logger.info(
            "[%s] agent=%s | START",
            call_id, agent_name,
        )
        if self._log_inputs:
            self.logger.debug(
                "[%s] agent=%s | INPUT args=%s kwargs=%s",
                call_id, agent_name,
                _truncate(args, self._max_output_chars),
                _truncate(kwargs, self._max_output_chars),
            )

        # --- async path ---
        if inspect.iscoroutinefunction(target):
            async def _run_async(*a: Any, **kw: Any) -> Any:
                t0 = time.perf_counter()
                try:
                    result = await target(*a, **kw)
                    elapsed = time.perf_counter() - t0
                    self.logger.info(
                        "[%s] agent=%s | FINISH latency=%.3fs",
                        call_id, agent_name, elapsed,
                    )
                    self.logger.debug(
                        "[%s] agent=%s | OUTPUT %s",
                        call_id, agent_name,
                        _truncate(result, self._max_output_chars),
                    )
                    return result
                except Exception as exc:
                    elapsed = time.perf_counter() - t0
                    self.logger.error(
                        "[%s] agent=%s | ERROR latency=%.3fs error=%s: %s",
                        call_id, agent_name, elapsed,
                        type(exc).__name__, exc,
                        exc_info=True,
                    )
                    raise

            return _run_async(*args, **kwargs)

        # --- sync path ---
        t0 = time.perf_counter()
        try:
            result = target(*args, **kwargs)
            elapsed = time.perf_counter() - t0
            self.logger.info(
                "[%s] agent=%s | FINISH latency=%.3fs",
                call_id, agent_name, elapsed,
            )
            self.logger.debug(
                "[%s] agent=%s | OUTPUT %s",
                call_id, agent_name,
                _truncate(result, self._max_output_chars),
            )
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            self.logger.error(
                "[%s] agent=%s | ERROR latency=%.3fs error=%s: %s",
                call_id, agent_name, elapsed,
                type(exc).__name__, exc,
                exc_info=True,
            )
            raise
