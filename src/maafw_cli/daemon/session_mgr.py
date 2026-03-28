"""
SessionManager — named sessions backed by :class:`Session`.

Each session holds a controller, Resource, ElementStore, and an asyncio Lock
for daemon concurrency protection.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.session import Session
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import DISPATCH

_log = logging.getLogger("maafw_cli.daemon.session_mgr")


class SessionManager:
    """Manages named sessions for the daemon.

    Tracks active sessions, default session, and provides execution routing.
    All mutations are protected by an asyncio.Lock for concurrency safety.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._default: str | None = None
        self._lock = asyncio.Lock()

    # ── ensure / add / get / close ───────────────────────────────

    async def ensure(self, name: str) -> Session:
        """Return the session *name*, creating an empty one if it doesn't exist.

        The first session created automatically becomes the default.
        """
        async with self._lock:
            if name in self._sessions:
                return self._sessions[name]

            session = Session(name=name)
            self._sessions[name] = session

            if self._default is None:
                self._default = name

            _log.info("Created empty session '%s'", name)
            return session

    async def add(
        self,
        name: str,
        controller: Any,
        type: str,
        device: str,
    ) -> Session:
        """Ensure session *name* exists and attach a controller to it."""
        session = await self.ensure(name)
        async with session.lock:
            session.attach(controller, type, device)
        return session

    def get(self, name: str | None = None) -> Session:
        """Get a session by name, or the default if *name* is None.

        Raises :class:`DeviceConnectionError` if no matching session.
        """
        if name is None:
            name = self._default
        if name is None or name not in self._sessions:
            target = name or "(no default)"
            raise DeviceConnectionError(f"No active session '{target}'. Connect to a device first.")
        return self._sessions[name]

    async def close(self, name: str) -> None:
        """Close and remove a session.  Raises KeyError if not found."""
        async with self._lock:
            if name not in self._sessions:
                raise KeyError(f"Session '{name}' not found.")
            await self._close_session_unlocked(name)

    async def close_all(self) -> None:
        """Close all sessions (for daemon shutdown)."""
        async with self._lock:
            for name in list(self._sessions):
                await self._close_session_unlocked(name)

    async def _close_session_unlocked(self, name: str) -> None:
        """Internal: destroy a session and update default. Must be called with lock held."""
        session = self._sessions.pop(name, None)
        if session is None:
            return

        # Try to destroy the controller (may block — run in thread)
        ctrl = session._controller
        if ctrl is not None:
            try:
                if hasattr(ctrl, "destroy"):
                    await asyncio.to_thread(ctrl.destroy)
            except Exception:
                _log.warning("Error destroying controller for session '%s'", name, exc_info=True)

        # Update default if needed
        if self._default == name:
            if self._sessions:
                self._default = next(iter(self._sessions))
            else:
                self._default = None

        _log.info("Closed session '%s'", name)

    # ── listing / default ───────────────────────────────────────

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return summary info for all sessions."""
        return [
            {
                "name": s.name,
                "type": s.type or None,
                "device": s.device or None,
                "connected": s.has_controller,
                "is_default": s.name == self._default,
            }
            for s in self._sessions.values()
        ]

    def set_default(self, name: str) -> None:
        """Set the default session.  Raises KeyError if not found."""
        if name not in self._sessions:
            raise KeyError(f"Session '{name}' not found.")
        self._default = name

    @property
    def default_name(self) -> str | None:
        return self._default

    @property
    def count(self) -> int:
        return len(self._sessions)

    @property
    def session_names(self) -> list[str]:
        return list(self._sessions.keys())

    # ── execution ───────────────────────────────────────────────

    async def execute(
        self,
        action: str,
        params: dict[str, Any],
        session_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a service action on a session.

        Looks up the action in DISPATCH, builds a ServiceContext,
        and runs the service function with per-session locking.

        Services marked with ``needs_session=False`` are executed directly
        without a session context (e.g. ``device_list``, ``resource_status``).

        For session-scoped services, the session is auto-created if it
        doesn't exist yet (via :meth:`ensure`).
        """
        service_fn = DISPATCH.get(action)
        if service_fn is None:
            raise ValueError(f"Unknown action: '{action}'")

        needs_session = getattr(service_fn, "needs_session", True)

        if not needs_session:
            result = await asyncio.to_thread(service_fn, **params)
            return result

        session = await self.ensure(session_name or self._default or "default")

        async with session.lock:
            svc_ctx = ServiceContext(session)
            result = await asyncio.to_thread(service_fn, svc_ctx, **params)
            return result
