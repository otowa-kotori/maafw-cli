"""
LocalExecutor — in-process service executor for daemon-free operation.

Mirrors :class:`~maafw_cli.daemon.session_mgr.SessionManager.execute`
but runs synchronously in the calling thread.  Used by ``repl --local``.
"""
from __future__ import annotations

import logging
from typing import Any

from maafw_cli.core.session import Session
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import DISPATCH

# Ensure all services are registered
import maafw_cli.services.interaction  # noqa: F401
import maafw_cli.services.vision  # noqa: F401
import maafw_cli.services.connection  # noqa: F401
import maafw_cli.services.resource  # noqa: F401
import maafw_cli.services.recognition  # noqa: F401

_log = logging.getLogger("maafw_cli.core.local_executor")


class LocalExecutor:
    """In-process service executor — no daemon, no IPC.

    Holds sessions locally and dispatches service calls synchronously.
    Connect commands are intercepted to attach controllers to sessions.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._default: str | None = None

    # ── public API ──────────────────────────────────────────────

    def execute(
        self,
        action: str,
        params: dict[str, Any],
        session: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch an action to the appropriate service function.

        Mirrors ``SessionManager.execute()`` but synchronous.
        """
        # Connect commands need special handling (they create sessions)
        if action == "connect_adb":
            return self._handle_connect_adb(params, session)
        if action == "connect_win32":
            return self._handle_connect_win32(params, session)

        # Built-in actions
        if action == "ping":
            return self._handle_ping()
        if action == "session_list":
            return {"sessions": self._list_sessions()}
        if action == "session_default":
            return self._handle_session_default(params)
        if action == "session_close":
            return self._handle_session_close(params)
        if action == "shutdown":
            _log.info("Shutdown requested in local mode (no-op)")
            return {"message": "Local mode — no daemon to shut down"}

        # Regular service dispatch
        service_fn = DISPATCH.get(action)
        if service_fn is None:
            raise ValueError(f"Unknown action: '{action}'")

        needs_session = getattr(service_fn, "needs_session", True)

        if not needs_session:
            return service_fn(**params)

        sess = self._get_or_create(session or self._default or "default")
        svc_ctx = ServiceContext(sess)
        return service_fn(svc_ctx, **params)

    def close_all(self) -> None:
        """Destroy all controllers (for cleanup)."""
        for name in list(self._sessions):
            self._close_session(name)

    # ── session management ──────────────────────────────────────

    def _get_or_create(self, name: str) -> Session:
        if name not in self._sessions:
            self._sessions[name] = Session(name=name)
            if self._default is None:
                self._default = name
            _log.info("Created local session '%s'", name)
        return self._sessions[name]

    def _close_session(self, name: str) -> None:
        session = self._sessions.pop(name, None)
        if session is None:
            return
        ctrl = session._controller
        if ctrl is not None and hasattr(ctrl, "destroy"):
            try:
                ctrl.destroy()
            except Exception:
                _log.warning("Error destroying controller for session '%s'", name, exc_info=True)
        if self._default == name:
            self._default = next(iter(self._sessions), None)
        _log.info("Closed local session '%s'", name)

    def _list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "type": s.type or None,
                "device": s.device or None,
                "connected": s.is_connected(),
                "is_default": s.name == self._default,
            }
            for s in self._sessions.values()
        ]

    # ── built-in action handlers ─────────────────────────────────

    def _handle_ping(self) -> dict[str, Any]:
        import os
        return {
            "pong": True,
            "mode": "local",
            "sessions": list(self._sessions.keys()),
            "pid": os.getpid(),
        }

    def _handle_session_default(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name") or None
        if not name:
            raise ValueError("session_default requires a non-empty 'name' parameter")
        if name not in self._sessions:
            raise KeyError(f"Session '{name}' not found.")
        self._default = name
        return {"default": name}

    def _handle_session_close(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name") or None
        if not name:
            raise ValueError("session_close requires a non-empty 'name' parameter")
        if name not in self._sessions:
            raise KeyError(f"Session '{name}' not found.")
        self._close_session(name)
        return {"closed": name}

    # ── connect handlers ─────────────────────────────────────────

    def _handle_connect_adb(
        self, params: dict[str, Any], session_name: str | None,
    ) -> dict[str, Any]:
        from maafw_cli.services.connection import _connect_adb_inner

        device = params.get("device", "")
        size = params.get("size", "short:720")
        screencap_method = params.get("screencap_method")
        input_method = params.get("input_method")
        name = session_name or params.get("session_name") or device

        result, controller = _connect_adb_inner(device, size, screencap_method, input_method)
        sess = self._get_or_create(name)
        sess.attach(controller, "adb", result["device"])
        self._default = name

        result["session"] = name
        return result

    def _handle_connect_win32(
        self, params: dict[str, Any], session_name: str | None,
    ) -> dict[str, Any]:
        from maafw_cli.services.connection import _connect_win32_inner

        window = params.get("window", "")
        screencap_method = params.get("screencap_method", "FramePool,PrintWindow")
        input_method = params.get("input_method", "PostMessage")
        size = params.get("size", "raw")
        name = session_name or params.get("session_name") or window

        result, controller = _connect_win32_inner(window, screencap_method, input_method, size)
        sess = self._get_or_create(name)
        sess.attach(controller, "win32", result["window_name"])
        self._default = name

        result["session"] = name
        return result
