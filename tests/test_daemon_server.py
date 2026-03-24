"""Tests for the daemon server — in-process asyncio, no subprocesses."""
from __future__ import annotations

import asyncio
import json
import os
import time

import pytest

from maafw_cli.daemon.protocol import encode, decode, make_request
from maafw_cli.daemon.server import DaemonServer, _pid_file, _port_file

# Import services to populate DISPATCH
import maafw_cli.services.interaction  # noqa: F401


# ── helpers ──────────────────────────────────────────────────────


async def _start_server(idle_timeout: float = 300) -> tuple[DaemonServer, int]:
    """Start a DaemonServer on port 0 (OS-assigned) and return (server, port)."""
    server = DaemonServer(port=0, idle_timeout=idle_timeout)
    server.port = await server._bind()
    # Get actual port from the underlying server
    actual_port = server._server.sockets[0].getsockname()[1]
    server.port = actual_port
    return server, actual_port


async def _send_recv(port: int, request: dict) -> dict:
    """Connect, send one request, read one response, close."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(encode(request))
    await writer.drain()
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    return decode(line)


# ── tests ────────────────────────────────────────────────────────


class TestDaemonServerPing:
    async def test_ping_response(self):
        server, port = await _start_server()
        # Run the client handler in background
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            req = make_request("ping")
            resp = await _send_recv(port, req)
            assert resp["ok"] is True
            assert resp["data"]["pong"] is True
            assert "uptime_seconds" in resp["data"]
            assert "pid" in resp["data"]
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()


class TestDaemonServerErrors:
    async def test_unknown_action(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            req = make_request("totally_bogus_action")
            resp = await _send_recv(port, req)
            assert resp["ok"] is False
            assert "Unknown action" in resp["error"]
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_malformed_json(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"{bad json}\n")
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert resp["ok"] is False
            assert "Malformed JSON" in resp["error"]
            writer.close()
            await writer.wait_closed()
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()


class TestDaemonServerShutdown:
    async def test_shutdown_command(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())

        req = make_request("shutdown")
        resp = await _send_recv(port, req)
        assert resp["ok"] is True
        assert "shutting down" in resp["data"]["message"].lower()

        # Verify shutdown was requested
        assert server._shutdown_event.is_set()

        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass
        server._server.close()
        await server._server.wait_closed()


class TestDaemonServerMultiClient:
    async def test_concurrent_clients(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            # Send 5 concurrent pings
            tasks = [_send_recv(port, make_request("ping")) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            assert all(r["ok"] for r in results)
            assert all(r["data"]["pong"] for r in results)
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()


class TestDaemonServerClientDisconnect:
    async def test_client_disconnect_server_continues(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            # Connect and immediately close
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()

            await asyncio.sleep(0.05)

            # Server should still be running — send another ping
            resp = await _send_recv(port, make_request("ping"))
            assert resp["ok"] is True
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()


class TestDaemonServerIdleWatchdog:
    async def test_idle_triggers_shutdown(self):
        # Use a very short idle timeout
        server, port = await _start_server(idle_timeout=0.2)
        serve_task = asyncio.create_task(server._server.serve_forever())
        watchdog_task = asyncio.create_task(server._idle_watchdog())

        # Wait for watchdog to fire
        try:
            await asyncio.wait_for(server._shutdown_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Idle watchdog did not trigger shutdown")

        assert server._shutdown_reason == "idle"

        serve_task.cancel()
        watchdog_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        server._server.close()
        await server._server.wait_closed()


class TestDaemonServerSessionActions:
    async def test_session_list_empty(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            resp = await _send_recv(port, make_request("session_list"))
            assert resp["ok"] is True
            assert resp["data"]["sessions"] == []
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_session_close_nonexistent(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            resp = await _send_recv(
                port,
                make_request("session_close", {"name": "nope"})
            )
            assert resp["ok"] is False
            assert "not found" in resp["error"]
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()


class TestDaemonServerPidPortFiles:
    async def test_pid_port_files_written(self, tmp_path, monkeypatch):
        # Redirect data dir to tmp
        monkeypatch.setattr("maafw_cli.daemon.server._data_dir", lambda: tmp_path)

        server = DaemonServer(port=0)
        server.port = await server._bind()
        actual_port = server._server.sockets[0].getsockname()[1]
        server.port = actual_port
        server._write_pid_port_files()

        pid_file = tmp_path / "daemon.pid"
        port_file = tmp_path / "daemon.port"

        assert pid_file.exists()
        assert port_file.exists()
        assert int(pid_file.read_text()) == os.getpid()
        assert int(port_file.read_text()) == actual_port

        server._server.close()
        await server._server.wait_closed()

    async def test_cleanup_removes_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.daemon.server._data_dir", lambda: tmp_path)

        server = DaemonServer(port=0)
        server.port = await server._bind()
        actual_port = server._server.sockets[0].getsockname()[1]
        server.port = actual_port
        server._write_pid_port_files()

        await server._cleanup()

        assert not (tmp_path / "daemon.pid").exists()
        assert not (tmp_path / "daemon.port").exists()


class TestDaemonServerMultipleRequests:
    async def test_multiple_requests_same_connection(self):
        """A single client can send multiple requests on one connection."""
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)

            # Send two pings on the same connection
            for i in range(3):
                req = make_request("ping", request_id=f"multi-{i}")
                writer.write(encode(req))
                await writer.drain()
                line = await reader.readline()
                resp = decode(line)
                assert resp["ok"] is True
                assert resp["id"] == f"multi-{i}"

            writer.close()
            await writer.wait_closed()
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()
