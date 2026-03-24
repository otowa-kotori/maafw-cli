"""Tests for daemon client IPC — uses in-process asyncio server."""
from __future__ import annotations

import asyncio
import os

import pytest

from maafw_cli.core.errors import MaafwError
from maafw_cli.core.ipc import (
    DaemonClient,
    _cleanup_stale_files,
    _is_process_alive,
    _read_daemon_info,
    ensure_daemon,
)
from maafw_cli.daemon.protocol import encode, decode, make_request
from maafw_cli.daemon.server import DaemonServer

# Import services to populate DISPATCH
import maafw_cli.services.interaction  # noqa: F401


# ── helpers ──────────────────────────────────────────────────────


async def _make_test_server() -> tuple[DaemonServer, int]:
    """Create a test server on OS-assigned port."""
    server = DaemonServer(port=0, idle_timeout=300)
    server.port = await server._bind()
    actual_port = server._server.sockets[0].getsockname()[1]
    server.port = actual_port
    return server, actual_port


# ── DaemonClient tests ──────────────────────────────────────────


class TestDaemonClient:
    async def test_send_ping(self):
        server, port = await _make_test_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            client = DaemonClient(port)
            result = await asyncio.to_thread(client.send, "ping")
            assert result["pong"] is True
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_send_unknown_action(self):
        server, port = await _make_test_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            client = DaemonClient(port)
            with pytest.raises(MaafwError, match="Unknown action"):
                await asyncio.to_thread(client.send, "totally_bogus")
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_connection_refused(self):
        client = DaemonClient(19798)  # Unlikely to be in use
        with pytest.raises((OSError, MaafwError)):
            await asyncio.to_thread(client.send, "ping")

    async def test_server_disconnect(self):
        """Server closes immediately after connection → should handle gracefully."""
        async def _bad_handler(reader, writer):
            writer.close()
            await writer.wait_closed()

        test_server = await asyncio.start_server(_bad_handler, "127.0.0.1", 0)
        port = test_server.sockets[0].getsockname()[1]

        try:
            client = DaemonClient(port)
            with pytest.raises((ValueError, MaafwError, OSError)):
                await asyncio.to_thread(client.send, "ping")
        finally:
            test_server.close()
            await test_server.wait_closed()


# ── Process lifecycle tests ─────────────────────────────────────


class TestProcessAlive:
    def test_current_pid_is_alive(self):
        assert _is_process_alive(os.getpid()) is True

    def test_invalid_pid(self):
        assert _is_process_alive(-1) is False
        assert _is_process_alive(0) is False

    def test_nonexistent_pid(self):
        # Use a very high PID that's unlikely to exist
        assert _is_process_alive(999999999) is False


class TestDaemonInfo:
    def test_read_daemon_info_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        pid, port = _read_daemon_info()
        assert pid is None
        assert port is None

    def test_read_daemon_info_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        (tmp_path / "daemon.pid").write_text("12345")
        (tmp_path / "daemon.port").write_text("19799")
        pid, port = _read_daemon_info()
        assert pid == 12345
        assert port == 19799

    def test_read_daemon_info_corrupt(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        (tmp_path / "daemon.pid").write_text("not-a-number")
        (tmp_path / "daemon.port").write_text("19799")
        pid, port = _read_daemon_info()
        assert pid is None

    def test_cleanup_stale_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        (tmp_path / "daemon.pid").write_text("12345")
        (tmp_path / "daemon.port").write_text("19799")
        _cleanup_stale_files()
        assert not (tmp_path / "daemon.pid").exists()
        assert not (tmp_path / "daemon.port").exists()


class TestEnsureDaemon:
    def test_daemon_already_running(self, tmp_path, monkeypatch):
        """If PID file has current process PID and port is reachable, return port."""
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._is_daemon_reachable", lambda port: True)
        (tmp_path / "daemon.pid").write_text(str(os.getpid()))
        (tmp_path / "daemon.port").write_text("19800")
        port = ensure_daemon()
        assert port == 19800

    def test_stale_pid_triggers_restart(self, tmp_path, monkeypatch):
        """If PID file points to dead process, clean up and try restart."""
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._is_daemon_reachable", lambda port: True)
        (tmp_path / "daemon.pid").write_text("999999999")
        (tmp_path / "daemon.port").write_text("19800")

        # Mock _start_daemon_process to write new PID/port files
        def fake_start():
            (tmp_path / "daemon.pid").write_text(str(os.getpid()))
            (tmp_path / "daemon.port").write_text("19801")

        monkeypatch.setattr("maafw_cli.core.ipc._start_daemon_process", fake_start)
        monkeypatch.setattr("maafw_cli.core.ipc._DAEMON_START_TIMEOUT", 2.0)

        port = ensure_daemon()
        assert port == 19801

    def test_timeout_raises_connection_error(self, tmp_path, monkeypatch):
        """If daemon doesn't start in time, raise ConnectionError."""
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)

        # _start_daemon_process does nothing — files never appear
        monkeypatch.setattr("maafw_cli.core.ipc._start_daemon_process", lambda: None)
        monkeypatch.setattr("maafw_cli.core.ipc._DAEMON_START_TIMEOUT", 0.3)
        monkeypatch.setattr("maafw_cli.core.ipc._DAEMON_POLL_INTERVAL", 0.05)

        with pytest.raises(MaafwError, match="Failed to start daemon"):
            ensure_daemon()
