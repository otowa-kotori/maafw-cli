"""
asyncio TCP server for the maafw-cli daemon.

Handles JSON-line requests, dispatches to SessionManager, and manages
PID/port files.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from typing import Any

from maafw_cli.core.errors import MaafwError
from maafw_cli.core.ipc import pid_file, port_file
from maafw_cli.paths import get_data_dir as _data_dir
from maafw_cli.daemon.protocol import decode, encode, error_response, ok_response
from maafw_cli.daemon.session_mgr import SessionManager

_log = logging.getLogger("maafw_cli.daemon.server")


def _summarize(d: dict[str, Any], max_len: int = 200) -> str:
    """Compact one-line summary of a result dict for logging."""
    import json
    s = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return s if len(s) <= max_len else s[:max_len] + "…"


_SENSITIVE_KEYS = frozenset({"token", "password", "secret", "key", "credential"})


def _sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *params* with sensitive values redacted for logging."""
    sanitized = {}
    for k, v in params.items():
        if any(sk in k.lower() for sk in _SENSITIVE_KEYS):
            sanitized[k] = "***"
        else:
            sanitized[k] = v
    return sanitized

# ── port / file constants ───────────────────────────────────────

DEFAULT_PORT = 19799
PORT_RANGE_END = 19810  # exclusive; try 19799-19809
# ── DaemonServer ────────────────────────────────────────────────


class DaemonServer:
    """asyncio TCP daemon server."""

    # Maximum size for a single JSON-line request (1 MB).
    MAX_LINE_LENGTH = 1 * 1024 * 1024

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
    ):
        self.host = host
        self.requested_port = port
        self.port: int = 0  # set after bind
        self.session_mgr = SessionManager()

        self._server: asyncio.Server | None = None
        self._start_time = time.monotonic()
        self._shutdown_event = asyncio.Event()
        self._shutdown_reason = "unknown"
        self._active_connections: int = 0

    # ── lifecycle ───────────────────────────────────────────────

    async def start(self) -> None:
        """Bind, write PID/port files, and serve forever."""
        self.port = await self._bind()
        self._install_signal_handlers()

        # Write PID/port files AFTER all initialization is complete,
        # so clients don't connect before the server is fully ready.
        self._write_pid_port_files()

        _log.info("Daemon listening on %s:%d", self.host, self.port)

        # Serve until shutdown
        await self._shutdown_event.wait()

        _log.info("Daemon shutting down (reason: %s)", self._shutdown_reason)
        await self._cleanup()

    async def _bind(self) -> int:
        """Find an available port and start the TCP server."""
        limit = self.MAX_LINE_LENGTH
        if self.requested_port is not None:
            self._server = await asyncio.start_server(
                self._handle_client, self.host, self.requested_port, limit=limit,
            )
            return self.requested_port

        # Try port range
        last_exc = None
        for port in range(DEFAULT_PORT, PORT_RANGE_END):
            try:
                self._server = await asyncio.start_server(
                    self._handle_client, self.host, port, limit=limit,
                )
                return port
            except OSError as e:
                last_exc = e
                continue

        raise RuntimeError(
            f"Cannot bind to any port in {DEFAULT_PORT}-{PORT_RANGE_END - 1}"
        ) from last_exc

    def _write_pid_port_files(self) -> None:
        """Write daemon.pid and daemon.port files."""
        data_dir = _data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)

        pid_file().write_text(str(os.getpid()), encoding="utf-8")
        port_file().write_text(str(self.port), encoding="utf-8")
        _log.debug("PID/port files written: pid=%d port=%d", os.getpid(), self.port)

    def _install_signal_handlers(self) -> None:
        """Install SIGTERM / SIGINT handlers for graceful shutdown.

        On Windows, ``loop.add_signal_handler`` raises ``NotImplementedError``
        for all signals.  The daemon runs headless (pythonw.exe, no console),
        so SIGINT has no source, and ``TerminateProcess`` (taskkill) is
        uninterceptable.  Graceful shutdown on Windows relies on the
        ``shutdown`` RPC command via ``daemon stop``.
        """
        loop = asyncio.get_running_loop()
        for sig_name in ("SIGTERM", "SIGINT"):
            sig = getattr(signal, sig_name, None)
            if sig is not None:
                try:
                    loop.add_signal_handler(sig, lambda s=sig_name: self._signal_shutdown(s))
                except NotImplementedError:
                    _log.debug("add_signal_handler(%s) not supported on this platform", sig_name)

    def _signal_shutdown(self, sig_name: str) -> None:
        _log.info("Received %s, initiating shutdown", sig_name)
        self._shutdown_reason = f"signal:{sig_name}"
        self._shutdown_event.set()

    async def _cleanup(self) -> None:
        """Graceful shutdown: stop server, drain connections, close sessions, remove files."""
        # Stop accepting new connections
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

        # Wait for active connections to drain (up to 5 seconds)
        drain_deadline = time.monotonic() + 5.0
        while self._active_connections > 0 and time.monotonic() < drain_deadline:
            await asyncio.sleep(0.1)
        if self._active_connections > 0:
            _log.warning("Forcing shutdown with %d active connection(s)", self._active_connections)

        # Close all sessions
        await self.session_mgr.close_all()

        # Remove PID/port files
        for f in (pid_file(), port_file()):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

        _log.info("Daemon cleanup complete")

    def request_shutdown(self, reason: str = "manual") -> None:
        """Request graceful shutdown (can be called from request handler)."""
        self._shutdown_reason = reason
        self._shutdown_event.set()

    # ── client connection handler ───────────────────────────────

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single client connection (may send multiple requests)."""
        peer = writer.get_extra_info("peername")
        self._active_connections += 1

        try:
            while True:
                try:
                    line = await reader.readuntil(b"\n")
                except asyncio.LimitOverrunError:
                    _log.warning("Client %s sent oversized message (>%d bytes), dropping",
                                 peer, reader._limit)
                    break
                except (ConnectionError, asyncio.IncompleteReadError):
                    break

                if not line:
                    break  # EOF

                response = await self._process_line(line)
                if response is not None:
                    writer.write(encode(response))
                    await writer.drain()
        except Exception:
            _log.warning("Error handling client %s", peer, exc_info=True)
        finally:
            self._active_connections -= 1
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_line(self, line: bytes) -> dict[str, Any] | None:
        """Parse one JSON-line and dispatch."""
        try:
            request = decode(line)
        except ValueError as e:
            _log.warning("Malformed request: %s", e)
            return error_response("?", str(e))

        req_id = request.get("id", "?")
        action = request.get("action", "")
        session_name = request.get("session")
        params = request.get("params", {})

        _log.info(">>> %s session=%s params=%s", action, session_name, _sanitize_params(params))
        t0 = time.monotonic()

        try:
            result = await self._dispatch(action, params, session_name, request)
            elapsed = int((time.monotonic() - t0) * 1000)
            _log.info("<<< %s OK %dms result=%s", action, elapsed, _summarize(result))
            return ok_response(req_id, result)
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            exit_code = getattr(e, "exit_code", 1) if isinstance(e, MaafwError) else 1
            _log.warning("<<< %s FAIL %dms: %s", action, elapsed, e)
            return error_response(req_id, str(e), exit_code=exit_code)

    async def _dispatch(
        self,
        action: str,
        params: dict[str, Any],
        session_name: str | None,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Route an action to the appropriate handler."""
        # ── built-in actions ────────────────────────────────────
        if action == "ping":
            return self._handle_ping()
        if action == "shutdown":
            self.request_shutdown("manual")
            return {"message": "Daemon shutting down"}
        if action == "session_list":
            return {"sessions": self.session_mgr.list_sessions()}
        if action == "session_default":
            name = params.get("name") or None
            if not name:
                raise ValueError("session_default requires a non-empty 'name' parameter")
            self.session_mgr.set_default(name)
            return {"default": name}
        if action == "session_close":
            name = params.get("name") or None
            if not name:
                raise ValueError("session_close requires a non-empty 'name' parameter")
            await self.session_mgr.close(name)
            return {"closed": name}

        # ── connect actions (create sessions) ───────────────────
        if action == "connect_adb":
            return await self._handle_connect_adb(params, request)
        if action == "connect_win32":
            return await self._handle_connect_win32(params, request)

        # ── regular service dispatch ────────────────────────────
        return await self.session_mgr.execute(action, params, session_name)

    def _handle_ping(self) -> dict[str, Any]:
        uptime = int(time.monotonic() - self._start_time)
        return {
            "pong": True,
            "uptime_seconds": uptime,
            "sessions": self.session_mgr.session_names,
            "pid": os.getpid(),
        }

    async def _handle_connect_adb(
        self, params: dict[str, Any], request: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle connect_adb: ensure session exists and attach controller."""
        from maafw_cli.services.connection import _connect_adb_inner

        device = params.get("device", "")
        size = params.get("size", "short:720")
        screencap_method = params.get("screencap_method")
        input_method = params.get("input_method")
        session_name = (
            request.get("session")
            or params.get("session_name")
            or device
        )

        result, controller = await asyncio.to_thread(
            _connect_adb_inner, device, size, screencap_method, input_method,
        )
        session = await self.session_mgr.ensure(session_name)
        async with session.lock:
            session.attach(controller, "adb", result["device"])

        result["session"] = session_name
        return result

    async def _handle_connect_win32(
        self, params: dict[str, Any], request: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle connect_win32: ensure session exists and attach controller."""
        from maafw_cli.services.connection import _connect_win32_inner

        window = params.get("window", "")
        screencap_method = params.get("screencap_method", "FramePool,PrintWindow")
        input_method = params.get("input_method", "PostMessage")
        size = params.get("size", "raw")
        session_name = (
            request.get("session")
            or params.get("session_name")
            or window
        )

        result, controller = await asyncio.to_thread(
            _connect_win32_inner, window, screencap_method, input_method, size,
        )
        session = await self.session_mgr.ensure(session_name)
        async with session.lock:
            session.attach(controller, "win32", result["window_name"])

        result["session"] = session_name
        return result
