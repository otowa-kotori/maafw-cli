"""
SessionManager — named sessions with controllers and elements in memory.

Each ``ManagedSession`` holds a Controller, ElementStore, SessionInfo,
and a per-session asyncio Lock for concurrency safety.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.session import SessionInfo
from maafw_cli.core.element import ElementStore
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import DISPATCH

_log = logging.getLogger("maafw_cli.daemon.session_mgr")


@dataclass
class ManagedSession:
    """A live daemon session — controller + metadata."""

    name: str
    controller: Any  # Controller (typed as Any to allow mocking)
    session_info: SessionInfo
    element_store: ElementStore = field(default_factory=lambda: ElementStore(path=None))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def make_service_context(self) -> ServiceContext:
        """Build a ServiceContext for executing service functions."""
        return ServiceContext(
            get_controller=lambda: self.controller,
            elements_path=None,
            session_type=self.session_info.type,
            element_store=self.element_store,
            session_name=self.name,
        )


class SessionManager:
    """Manages named sessions for the daemon.

    Tracks active sessions, default session, and provides execution routing.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ManagedSession] = {}
        self._default: str | None = None

    # ── add / get / close ───────────────────────────────────────

    def add(
        self,
        name: str,
        controller: Any,
        session_info: SessionInfo,
    ) -> ManagedSession:
        """Add a named session.  If *name* already exists, close the old one first."""
        if name in self._sessions:
            _log.info("Replacing existing session '%s'", name)
            self._close_session(name)

        session = ManagedSession(
            name=name,
            controller=controller,
            session_info=session_info,
        )
        self._sessions[name] = session

        # First session becomes default automatically
        if self._default is None:
            self._default = name

        _log.info("Added session '%s' (type=%s, device=%s)", name, session_info.type, session_info.device)
        return session

    def get(self, name: str | None = None) -> ManagedSession:
        """Get a session by name, or the default if *name* is None.

        Raises :class:`ConnectionError` if no matching session.
        """
        if name is None:
            name = self._default
        if name is None or name not in self._sessions:
            target = name or "(no default)"
            raise DeviceConnectionError(f"No active session '{target}'. Connect to a device first.")
        return self._sessions[name]

    def close(self, name: str) -> None:
        """Close and remove a session.  Raises KeyError if not found."""
        if name not in self._sessions:
            raise KeyError(f"Session '{name}' not found.")
        self._close_session(name)

    def close_all(self) -> None:
        """Close all sessions (for daemon shutdown)."""
        for name in list(self._sessions):
            self._close_session(name)

    def _close_session(self, name: str) -> None:
        """Internal: destroy a session and update default."""
        session = self._sessions.pop(name, None)
        if session is None:
            return

        # Try to destroy the controller
        try:
            if hasattr(session.controller, "destroy"):
                session.controller.destroy()
        except Exception:
            _log.warning("Error destroying controller for session '%s'", name, exc_info=True)

        # Update default if needed
        if self._default == name:
            if self._sessions:
                # Pick the most recently added remaining session
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
                "type": s.session_info.type,
                "device": s.session_info.device,
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
        """
        service_fn = DISPATCH.get(action)
        if service_fn is None:
            raise ValueError(f"Unknown action: '{action}'")

        needs_session = getattr(service_fn, "needs_session", True)

        if not needs_session:
            # Global service — no session required, run in thread directly
            result = await asyncio.to_thread(service_fn, **params)
            return result

        session = self.get(session_name)

        async with session.lock:
            svc_ctx = session.make_service_context()
            # Service functions do blocking I/O — run in thread
            result = await asyncio.to_thread(service_fn, svc_ctx, **params)
            return result
