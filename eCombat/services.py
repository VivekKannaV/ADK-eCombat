"""services.py — ADK service registry configuration for eCombat.

ADK discovers this file automatically when the agent directory contains it.
It registers the Redis-backed session service under the ``redis://`` URI
scheme, so that running::

    adk run --session_service_uri redis://:password@localhost:6379/0 eCombat

persists sessions (including working-context state) across process restarts.

If ``SESSION_SERVICE_URI`` is set in the environment, it is also read here
and registered as the default, allowing zero-argument ``adk run eCombat``
to use Redis automatically.
"""

from __future__ import annotations

import logging
import os

from google.adk.cli.service_registry import get_service_registry

from eCombat.src.services.session_service import RedisSessionService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register the Redis session service factory for the ``redis://`` scheme.
# ---------------------------------------------------------------------------


def _redis_factory(uri: str, **_kwargs) -> RedisSessionService:  # noqa: ANN001
    """Factory called by ADK when session_service_uri starts with ``redis://``."""
    logger.info("Initialising RedisSessionService with URI: redis://<redacted>")
    return RedisSessionService(uri=uri)


_registry = get_service_registry()
_registry.register_session_service("redis", _redis_factory)

logger.debug("RedisSessionService registered under scheme 'redis'")
