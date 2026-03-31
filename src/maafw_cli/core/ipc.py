"""
Daemon client IPC — ``DaemonClient`` and ``ensure_daemon()``.

Handles daemon process lifecycle and provides a synchronous client
for sending requests to the daemon server.
"""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from maafw_cli.core.errors import DeviceConnectionError, VersionMismatchError
from maafw_cli.paths import get_data_dir as _data_dir
from maafw_cli.daemon.protocol import decode, encode, make_request

_log = logging.getLogger("maafw_cli.ipc")

# ── PID / port file helpers ─────────────────────────────────────

_DAEMON_START_TIMEOUT = 10.0  # seconds to wait for daemon to start
_DAEMON_POLL_INTERVAL = 0.1   # polling interval when waiting


def pid_file() -> Path:
    """Path to the daemon PID file."""
    return _data_dir() / "daemon.pid"


def port_file() -> Path:
    """Path to the daemon port file."""
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
    pid_path = pid_file()
    port_path = port_file()

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
    for f in (pid_file(), port_file()):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def _start_daemon_process(*, verbose: bool = False) -> None:
    """Launch the daemon as a detached subprocess.

    When *verbose* is True, passes ``--verbose`` to the daemon process
    so it also logs to stderr.
    """
    cmd = [sys.executable, "-m", "maafw_cli.daemon"]
    if verbose:
        cmd.append("--verbose")

    if sys.platform == "win32":
        # CREATE_NO_WINDOW prevents any console/window from appearing.
        # Do NOT combine with DETACHED_PROCESS — they conflict and
        # DETACHED_PROCESS takes precedence, which may allocate a
        # new visible console.
        # Use pythonw.exe when available (no console at all).
        exe_path = Path(sys.executable)
        pythonw = exe_path.with_name("pythonw.exe")
        if pythonw.exists():
            cmd[0] = str(pythonw)

        _daemon_proc = subprocess.Popen(  # noqa: F841 — prevent GC of kernel handle
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    else:
        _daemon_proc = subprocess.Popen(  # noqa: F841
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )


def ensure_daemon(*, check_version: bool = True, verbose: bool = False) -> int:
    """Ensure the daemon is running and return its port.

    Starts a new daemon if needed. Raises :class:`DeviceConnectionError`
    if the daemon cannot be started within the timeout.

    When *check_version* is True (default), pings the daemon and verifies
    its version matches the CLI. Raises :class:`VersionMismatchError` on
    mismatch.

    When *verbose* is True, the daemon process is started with
    ``--verbose`` so it also logs to stderr.
    """
    t0 = time.perf_counter()

    pid, port = _read_daemon_info()

    # Case 1: PID/port files exist — verify daemon is actually reachable
    if pid is not None and port is not None:
        if _is_process_alive(pid) and _is_daemon_reachable(port):
            elapsed = int((time.perf_counter() - t0) * 1000)
            _log.debug("ensure_daemon: %dms (already running, pid=%d port=%d)", elapsed, pid, port)
            if check_version:
                _check_daemon_version(port)
            return port
        # Stale files
        _log.debug("Stale daemon files (pid=%s, port=%s), cleaning up", pid, port)
        _cleanup_stale_files()

    # Case 2: start new daemon — use file lock to prevent concurrent starts
    from maafw_cli.core.filelock import FileLock, FileLockError

    lock_path = _data_dir() / "daemon.lock"
    try:
        with FileLock(lock_path):
            # Double-check inside the lock — another process may have started
            # the daemon between our initial check and acquiring the lock.
            pid, port = _read_daemon_info()
            if pid is not None and port is not None:
                if _is_process_alive(pid) and _is_daemon_reachable(port):
                    if check_version:
                        _check_daemon_version(port)
                    return port
                _cleanup_stale_files()

            _log.info("Starting daemon...")
            _start_daemon_process(verbose=verbose)
    except FileLockError:
        _log.debug("Another process is starting the daemon, waiting...")

    # Wait for daemon to become ready (files appear + port reachable)
    deadline = time.perf_counter() + _DAEMON_START_TIMEOUT
    while time.perf_counter() < deadline:
        time.sleep(_DAEMON_POLL_INTERVAL)
        pid, port = _read_daemon_info()
        if pid is not None and port is not None and _is_daemon_reachable(port):
            _log.info("Daemon started: pid=%d port=%d", pid, port)
            return port

    log_path = _data_dir() / "daemon.log"
    raise DeviceConnectionError(
        f"Failed to start daemon within timeout. Check {log_path} for details."
    )


def _check_daemon_version(port: int) -> None:
    """Ping the daemon and verify its version matches the CLI."""
    from maafw_cli import __version__ as cli_version

    try:
        client = DaemonClient(port)
        data = client.send("ping")
    except Exception:
        # If ping fails, don't block — let the real request fail naturally
        _log.debug("Version check ping failed, skipping")
        return

    daemon_version = data.get("version")
    if daemon_version != cli_version:
        raise VersionMismatchError(cli_version, daemon_version)


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

        Raises :class:`DeviceConnectionError` on communication failure.
        Raises the appropriate :class:`MaafwError` if the daemon returns an error.
        """
        request = make_request(action, params, session=session)
        if session_name is not None:
            request["session_name"] = session_name

        t0 = time.perf_counter()
        try:
            response = self._sync_send(request)
        except OSError as e:
            raise DeviceConnectionError(f"Failed to communicate with daemon: {e}")
        elapsed = int((time.perf_counter() - t0) * 1000)
        _log.debug("IPC %s: %dms (round-trip)", action, elapsed)

        if not response.get("ok"):
            error_msg = response.get("error", "Unknown daemon error")
            exit_code = response.get("exit_code", 1)
            from maafw_cli.core.errors import MaafwError
            raise MaafwError(error_msg, exit_code=exit_code)

        return response.get("data", {})

    def _sync_send(self, request: dict) -> dict:
        """Connect, send request, read response — pure synchronous socket.

        Skips server-side heartbeat messages and waits for the real response.
        Socket timeout is 60s (heartbeats arrive every 15s, so 60s without
        any data means the daemon is dead).
        """
        sock = socket.create_connection((self.host, self.port), timeout=5.0)
        try:
            sock.settimeout(60.0)  # heartbeat every 15s; 60s = 4× margin
            sock.sendall(encode(request))
            reader = sock.makefile("rb")
            try:
                while True:
                    line = reader.readline()
                    if not line:
                        raise DeviceConnectionError(
                            "Daemon closed connection unexpectedly"
                        )
                    msg = decode(line)
                    if msg.get("heartbeat"):
                        continue  # skip heartbeat, keep waiting
                    return msg
            finally:
                reader.close()
        finally:
            sock.close()


# ── public helpers for daemon management ─────────────────────────


def get_daemon_info() -> tuple[int | None, int | None]:
    """Return (pid, port) of a running daemon, or (None, None).

    Also verifies the process is alive; stale files return (None, None).
    """
    pid, port = _read_daemon_info()
    if pid is None or port is None:
        return None, None
    if not _is_process_alive(pid):
        return None, None
    return pid, port
