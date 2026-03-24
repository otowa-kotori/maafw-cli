"""
Daemon client IPC — ``DaemonClient`` and ``ensure_daemon()``.

Handles daemon process lifecycle and provides a synchronous client
for sending requests to the daemon server.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from maafw_cli.core.errors import ConnectionError as MaafwConnectionError
from maafw_cli.core.session import _data_dir
from maafw_cli.daemon.protocol import decode, encode, make_request

_log = logging.getLogger("maafw_cli.ipc")

# ── PID / port file helpers ─────────────────────────────────────

_DAEMON_START_TIMEOUT = 10.0  # seconds to wait for daemon to start
_DAEMON_POLL_INTERVAL = 0.1   # polling interval when waiting


def _pid_file() -> Path:
    return _data_dir() / "daemon.pid"


def _port_file() -> Path:
    return _data_dir() / "daemon.port"


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running.

    On Windows, ``os.kill(pid, 0)`` does NOT work reliably (it may
    actually terminate the process or raise WinError 87).  We use
    ``kernel32.OpenProcess`` instead.
    """
    if pid <= 0:
        return False

    if sys.platform == "win32":
        return _is_process_alive_win32(pid)

    # POSIX: signal 0 just checks existence
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _is_process_alive_win32(pid: int) -> bool:
    """Windows-specific process check via OpenProcess."""
    import ctypes
    import ctypes.wintypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        exit_code = ctypes.wintypes.DWORD()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return exit_code.value == STILL_ACTIVE
        return False
    finally:
        kernel32.CloseHandle(handle)


def _is_daemon_reachable(port: int, host: str = "127.0.0.1") -> bool:
    """Quick TCP connect check — verifies the daemon is actually listening."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (OSError, TimeoutError):
        return False


def _read_daemon_info() -> tuple[int | None, int | None]:
    """Read PID and port from daemon files. Returns (pid, port) or (None, None)."""
    pid_path = _pid_file()
    port_path = _port_file()

    if not pid_path.exists() or not port_path.exists():
        return None, None

    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        port = int(port_path.read_text(encoding="utf-8").strip())
        return pid, port
    except (ValueError, OSError):
        return None, None


def _cleanup_stale_files() -> None:
    """Remove PID/port files if the daemon process is dead."""
    for f in (_pid_file(), _port_file()):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def _start_daemon_process() -> None:
    """Launch the daemon as a detached subprocess."""
    cmd = [sys.executable, "-m", "maafw_cli.daemon"]

    if sys.platform == "win32":
        # CREATE_NO_WINDOW — no console flash; DETACHED_PROCESS — detach
        # from parent console so the daemon survives the CLI exiting.
        flags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        )
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )


def ensure_daemon() -> int:
    """Ensure the daemon is running and return its port.

    Starts a new daemon if needed. Raises :class:`MaafwConnectionError`
    if the daemon cannot be started within the timeout.
    """
    pid, port = _read_daemon_info()

    # Case 1: PID/port files exist — verify daemon is actually reachable
    if pid is not None and port is not None:
        if _is_process_alive(pid) and _is_daemon_reachable(port):
            _log.debug("Daemon already running: pid=%d port=%d", pid, port)
            return port
        # Stale files
        _log.debug("Stale daemon files (pid=%s, port=%s), cleaning up", pid, port)
        _cleanup_stale_files()

    # Case 2: start new daemon
    _log.info("Starting daemon...")
    _start_daemon_process()

    # Wait for daemon to become ready (files appear + port reachable)
    deadline = time.monotonic() + _DAEMON_START_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(_DAEMON_POLL_INTERVAL)
        pid, port = _read_daemon_info()
        if pid is not None and port is not None and _is_daemon_reachable(port):
            _log.info("Daemon started: pid=%d port=%d", pid, port)
            return port

    log_path = _data_dir() / "daemon.log"
    raise MaafwConnectionError(
        f"Failed to start daemon within timeout. Check {log_path} for details."
    )


# ── DaemonClient ────────────────────────────────────────────────


class DaemonClient:
    """Synchronous client for communicating with the daemon."""

    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.host = host
        self.port = port

    def send(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        session: str | None = None,
        session_name: str | None = None,
    ) -> dict[str, Any]:
        """Send a request and return the response data.

        Raises :class:`MaafwConnectionError` on communication failure.
        Raises the appropriate :class:`MaafwError` if the daemon returns an error.
        """
        request = make_request(action, params, session=session)
        if session_name is not None:
            request["session_name"] = session_name

        try:
            response = asyncio.run(self._async_send(request))
        except (OSError, asyncio.TimeoutError) as e:
            raise MaafwConnectionError(f"Failed to communicate with daemon: {e}")

        if not response.get("ok"):
            error_msg = response.get("error", "Unknown daemon error")
            exit_code = response.get("exit_code", 1)
            from maafw_cli.core.errors import MaafwError
            raise MaafwError(error_msg, exit_code=exit_code)

        return response.get("data", {})

    async def _async_send(self, request: dict) -> dict:
        """Connect, send request, read response."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=5.0,
        )
        try:
            writer.write(encode(request))
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=30.0)
            if not line:
                raise MaafwConnectionError("Daemon closed connection unexpectedly")
            return decode(line)
        finally:
            writer.close()
            await writer.wait_closed()
