"""Tests for daemon client IPC — uses in-process asyncio server."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from maafw_cli.core.errors import MaafwError, VersionMismatchError
from maafw_cli.core.ipc import (
    DaemonClient,
    _cleanup_stale_files,
    _is_process_alive,
    _read_daemon_info,
    _start_daemon_process,
    ensure_daemon,
)
from maafw_cli.daemon.protocol import encode, decode, make_request
from maafw_cli.daemon.server import DaemonServer

# Import services to populate DISPATCH
import maafw_cli.services.interaction  # noqa: F401


# ── helpers ──────────────────────────────────────────────────────


async def _make_test_server() -> tuple[DaemonServer, int]:
    """Create a test server on OS-assigned port."""
    server = DaemonServer(port=0)
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


class TestStartDaemonProcess:
    def test_pythonw_uses_path_with_name(self, tmp_path):
        """_start_daemon_process should use Path.with_name for pythonw.exe,
        not str.replace which breaks when 'python.exe' appears in parent dirs."""
        # Create a dir whose name contains "python.exe" to trip up str.replace
        fake_dir = tmp_path / "python.exe_is_in_this_dir"
        fake_dir.mkdir()
        fake_python = fake_dir / "python.exe"
        fake_pythonw = fake_dir / "pythonw.exe"
        fake_python.write_text("fake")
        fake_pythonw.write_text("fake")

        with patch.object(sys, "executable", str(fake_python)), \
             patch.object(sys, "platform", "win32"), \
             patch("maafw_cli.core.ipc.subprocess.Popen") as mock_popen:
            _start_daemon_process()
            cmd = mock_popen.call_args[0][0]
            assert cmd[0] == str(fake_pythonw)


# ── Version check tests ──────────────────────────────────────


class TestVersionCheck:
    async def test_version_match_passes(self, tmp_path, monkeypatch):
        """ensure_daemon with check_version=True should pass when versions match."""
        server, port = await _make_test_server()
        serve_task = asyncio.create_task(server._server.serve_forever())

        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._is_daemon_reachable", lambda p: True)
        (tmp_path / "daemon.pid").write_text(str(os.getpid()))
        (tmp_path / "daemon.port").write_text(str(port))

        try:
            # Versions match — should not raise
            result_port = await asyncio.to_thread(ensure_daemon, check_version=True)
            assert result_port == port
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_version_mismatch_raises(self, tmp_path, monkeypatch):
        """ensure_daemon should raise VersionMismatchError when versions differ."""
        server, port = await _make_test_server()
        serve_task = asyncio.create_task(server._server.serve_forever())

        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._is_daemon_reachable", lambda p: True)
        (tmp_path / "daemon.pid").write_text(str(os.getpid()))
        (tmp_path / "daemon.port").write_text(str(port))

        # Fake CLI version to differ from daemon
        monkeypatch.setattr("maafw_cli.core.ipc.VersionMismatchError", VersionMismatchError)
        import maafw_cli.core.ipc as ipc_mod

        original_check = ipc_mod._check_daemon_version

        def fake_check(p):
            """Simulate mismatch by patching __version__ during the check."""
            with patch("maafw_cli.__version__", "99.99.99"):
                original_check(p)

        monkeypatch.setattr("maafw_cli.core.ipc._check_daemon_version", fake_check)

        try:
            with pytest.raises(VersionMismatchError):
                await asyncio.to_thread(ensure_daemon, check_version=True)
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_check_version_false_skips(self, tmp_path, monkeypatch):
        """ensure_daemon(check_version=False) should not check version."""
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._is_daemon_reachable", lambda p: True)
        (tmp_path / "daemon.pid").write_text(str(os.getpid()))
        (tmp_path / "daemon.port").write_text("19800")

        # Should return immediately without version check
        result_port = ensure_daemon(check_version=False)
        assert result_port == 19800

    def test_version_mismatch_error_message(self):
        """VersionMismatchError should include both versions and fix instruction."""
        err = VersionMismatchError("1.0.0", "0.9.0")
        assert "1.0.0" in str(err)
        assert "0.9.0" in str(err)
        assert "daemon restart" in str(err)
        assert err.exit_code == 4

    def test_version_mismatch_error_unknown_daemon(self):
        """VersionMismatchError with None daemon version."""
        err = VersionMismatchError("1.0.0", None)
        assert "unknown" in str(err)


# ── Client heartbeat skip tests ──────────────────────────────


class TestClientHeartbeatSkip:
    async def test_client_skips_heartbeat_lines(self):
        """DaemonClient._sync_send should skip heartbeat lines and return real response."""
        async def heartbeat_handler(reader, writer):
            line = await reader.readline()
            # Send 2 heartbeats then the real response
            for i in range(2):
                writer.write(encode({"heartbeat": True, "elapsed": i * 15}))
                await writer.drain()
            # Send real response
            request = decode(line)
            resp = {"ok": True, "id": request.get("id", "?"), "data": {"pong": True}}
            writer.write(encode(resp))
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        test_server = await asyncio.start_server(heartbeat_handler, "127.0.0.1", 0)
        port = test_server.sockets[0].getsockname()[1]

        try:
            client = DaemonClient(port)
            result = await asyncio.to_thread(client.send, "ping")
            assert result["pong"] is True
        finally:
            test_server.close()
            await test_server.wait_closed()

    async def test_client_handles_no_heartbeat(self):
        """DaemonClient works normally when server sends no heartbeats."""
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
