"""session_service.py — Redis-backed ADK session service.

Implements ``BaseSessionService`` so that ADK sessions — including the
working-context state fields — survive process restarts.

Redis key layout
----------------
``adk:session:{app}:{user}:{session_id}``
    JSON blob containing ``id``, ``app_name``, ``user_id``, ``state`` (dict)
    and ``last_update_time`` (float).

``adk:events:{app}:{user}:{session_id}``
    JSON list of serialised ``Event`` objects for that session.

``adk:app_state:{app}``
    JSON dict for app-scoped state (``app:`` prefix keys, stored raw).

``adk:user_state:{app}:{user}``
    JSON dict for user-scoped state (``user:`` prefix keys, stored raw).

``adk:session_ids:{app}:{user}``
    Redis Set of every session ID created for this (app, user) pair.

``adk:user_ids:{app}``
    Redis Set of every user ID seen for this app.

Working-context fields tracked in ``session.state``
----------------------------------------------------
* ``current_order_id``      – most-recently referenced order
* ``current_customer_name`` – customer name provided in this session
* ``current_product_id``    – most-recently referenced product
* ``last_intent``           – last classified user intent
* ``last_lookup_key``       – last free-text lookup key used
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import redis
from typing_extensions import override

from google.adk.events.event import Event
from google.adk.sessions.base_session_service import (
    BaseSessionService,
    GetSessionConfig,
    ListSessionsResponse,
)
from google.adk.sessions.session import Session
from google.adk.sessions.state import State

from eCombat.src.config.settings import (
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_TTL = 60 * 60 * 24  # 24 hours
_KEY_PREFIX = "adk"

# ---------------------------------------------------------------------------
# Working-context field names stored in session.state
# ---------------------------------------------------------------------------

CONTEXT_FIELDS = frozenset(
    {
        "current_order_id",
        "current_customer_name",
        "current_product_id",
        "last_intent",
        "last_lookup_key",
    }
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _session_key(app: str, user: str, session_id: str) -> str:
    return f"{_KEY_PREFIX}:session:{app}:{user}:{session_id}"


def _events_key(app: str, user: str, session_id: str) -> str:
    return f"{_KEY_PREFIX}:events:{app}:{user}:{session_id}"


def _app_state_key(app: str) -> str:
    return f"{_KEY_PREFIX}:app_state:{app}"


def _user_state_key(app: str, user: str) -> str:
    return f"{_KEY_PREFIX}:user_state:{app}:{user}"


def _session_ids_key(app: str, user: str) -> str:
    return f"{_KEY_PREFIX}:session_ids:{app}:{user}"


def _user_ids_key(app: str) -> str:
    return f"{_KEY_PREFIX}:user_ids:{app}"


def _encode(obj: Any) -> str:
    return json.dumps(obj, default=str)


def _decode(raw: str | bytes | None) -> Any:
    if raw is None:
        return None
    return json.loads(raw)


# ---------------------------------------------------------------------------
# RedisSessionService
# ---------------------------------------------------------------------------


class RedisSessionService(BaseSessionService):
    """A Redis-backed ``BaseSessionService`` for durable ADK sessions.

    Pass ``uri="redis://[password@]host:port/db"`` when constructing, *or*
    let it fall back to the individual ``REDIS_*`` settings from
    ``eCombat.src.config.settings``.

    Usage (via ADK CLI)::

        adk run --session_service_uri redis://:password@localhost:6379/0 eCombat

    Usage (in services.py)::

        from google.adk.cli.service_registry import get_service_registry
        from eCombat.src.services.session_service import RedisSessionService

        get_service_registry().register_session_service(
            "redis",
            lambda uri, **kw: RedisSessionService(uri=uri),
        )
    """

    def __init__(
        self,
        *,
        uri: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> None:
        if uri:
            self._pool = redis.ConnectionPool.from_url(
                uri, decode_responses=True
            )
        else:
            self._pool = redis.ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD or None,
                decode_responses=True,
            )
        self._ttl = ttl

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _client(self) -> redis.Redis:
        return redis.Redis(connection_pool=self._pool)

    def _load_session(
        self,
        r: redis.Redis,
        app: str,
        user: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        raw = r.get(_session_key(app, user, session_id))
        if raw is None:
            return None

        data: dict[str, Any] = _decode(raw)

        # Merge app + user state into the session state for callers
        app_state = _decode(r.get(_app_state_key(app))) or {}
        user_state = _decode(r.get(_user_state_key(app, user))) or {}

        merged_state: dict[str, Any] = {}
        merged_state.update(
            {f"{State.APP_PREFIX}{k}": v for k, v in app_state.items()}
        )
        merged_state.update(
            {f"{State.USER_PREFIX}{k}": v for k, v in user_state.items()}
        )
        merged_state.update(data.get("state", {}))

        # Load events with optional filtering
        raw_events = r.get(_events_key(app, user, session_id))
        all_events: list[dict[str, Any]] = _decode(raw_events) or []

        if config is not None:
            if config.num_recent_events is not None:
                if config.num_recent_events == 0:
                    all_events = []
                else:
                    all_events = all_events[-config.num_recent_events :]
            if config.after_timestamp is not None:
                all_events = [
                    e
                    for e in all_events
                    if e.get("timestamp", 0) >= config.after_timestamp
                ]

        events = [Event.model_validate(e) for e in all_events]

        return Session(
            id=session_id,
            app_name=app,
            user_id=user,
            state=merged_state,
            events=events,
            last_update_time=data.get("last_update_time", 0.0),
        )

    def _persist_session(
        self,
        r: redis.Redis,
        session: Session,
    ) -> None:
        """Write session metadata + state to Redis atomically."""
        app = session.app_name
        user = session.user_id
        sid = session.id

        # Split state into scopes
        app_delta: dict[str, Any] = {}
        user_delta: dict[str, Any] = {}
        session_state: dict[str, Any] = {}

        for key, value in session.state.items():
            if key.startswith(State.APP_PREFIX):
                app_delta[key.removeprefix(State.APP_PREFIX)] = value
            elif key.startswith(State.USER_PREFIX):
                user_delta[key.removeprefix(State.USER_PREFIX)] = value
            elif not key.startswith(State.TEMP_PREFIX):
                session_state[key] = value

        now = time.time()
        session_blob = {
            "id": sid,
            "app_name": app,
            "user_id": user,
            "state": session_state,
            "last_update_time": now,
        }
        events_data = [e.model_dump(mode="json") for e in session.events]

        pipe = r.pipeline()
        pipe.set(_session_key(app, user, sid), _encode(session_blob))
        pipe.set(_events_key(app, user, sid), _encode(events_data))
        if self._ttl > 0:
            pipe.expire(_session_key(app, user, sid), self._ttl)
            pipe.expire(_events_key(app, user, sid), self._ttl)

        if app_delta:
            raw_app = r.get(_app_state_key(app))
            existing_app = _decode(raw_app) or {}
            existing_app.update(app_delta)
            pipe.set(_app_state_key(app), _encode(existing_app))

        if user_delta:
            raw_user = r.get(_user_state_key(app, user))
            existing_user = _decode(raw_user) or {}
            existing_user.update(user_delta)
            pipe.set(_user_state_key(app, user), _encode(existing_user))

        # Track session/user membership sets
        pipe.sadd(_session_ids_key(app, user), sid)
        pipe.sadd(_user_ids_key(app), user)
        if self._ttl > 0:
            pipe.expire(_session_ids_key(app, user), self._ttl)

        pipe.execute()

    # ------------------------------------------------------------------
    # BaseSessionService interface
    # ------------------------------------------------------------------

    @override
    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        import uuid as _uuid

        sid = (session_id or _uuid.uuid4().hex).strip()
        r = self._client()

        if r.exists(_session_key(app_name, user_id, sid)):
            from google.adk.errors.already_exists_error import AlreadyExistsError
            raise AlreadyExistsError(f"Session {sid!r} already exists.")

        session = Session(
            id=sid,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=time.time(),
        )
        self._persist_session(r, session)
        logger.debug("Created session %r for user %r in app %r", sid, user_id, app_name)
        return await self.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=sid,
        )  # type: ignore[return-value]

    @override
    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        r = self._client()
        return self._load_session(r, app_name, user_id, session_id, config)

    @override
    async def list_sessions(
        self,
        *,
        app_name: str,
        user_id: Optional[str] = None,
    ) -> ListSessionsResponse:
        r = self._client()
        sessions: list[Session] = []

        if user_id is not None:
            user_ids = [user_id]
        else:
            user_ids = list(r.smembers(_user_ids_key(app_name)))

        for uid in user_ids:
            for sid in r.smembers(_session_ids_key(app_name, uid)):
                raw = r.get(_session_key(app_name, uid, sid))
                if raw is None:
                    continue
                data = _decode(raw)
                sessions.append(
                    Session(
                        id=sid,
                        app_name=app_name,
                        user_id=uid,
                        state={},
                        events=[],
                        last_update_time=data.get("last_update_time", 0.0),
                    )
                )
        return ListSessionsResponse(sessions=sessions)

    @override
    async def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        r = self._client()
        pipe = r.pipeline()
        pipe.delete(_session_key(app_name, user_id, session_id))
        pipe.delete(_events_key(app_name, user_id, session_id))
        pipe.srem(_session_ids_key(app_name, user_id), session_id)
        pipe.execute()
        logger.debug(
            "Deleted session %r for user %r in app %r",
            session_id,
            user_id,
            app_name,
        )

    @override
    async def append_event(self, session: Session, event: Event) -> Event:
        """Persist the event and any state delta to Redis."""
        event = await super().append_event(session, event)

        r = self._client()
        self._persist_session(r, session)
        return event

    @override
    async def get_user_state(
        self, *, app_name: str, user_id: str
    ) -> dict[str, Any]:
        r = self._client()
        raw = r.get(_user_state_key(app_name, user_id))
        return _decode(raw) or {}
