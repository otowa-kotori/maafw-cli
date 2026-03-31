"""Tests for the daemon server — in-process asyncio, no subprocesses."""
from __future__ import annotations

import asyncio
import os

import pytest

from maafw_cli.daemon.protocol import encode, decode, make_request
from maafw_cli.daemon.server import DaemonServer, _sanitize_params

# Import services to populate DISPATCH
import maafw_cli.services.interaction  # noqa: F401


# ── helpers ──────────────────────────────────────────────────────


async def _start_server() -> tuple[DaemonServer, int]:
    """Start a DaemonServer on port 0 (OS-assigned) and return (server, port)."""
    server = DaemonServer(port=0)
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

    async def test_ping_includes_version(self):
        from maafw_cli import __version__

        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            req = make_request("ping")
            resp = await _send_recv(port, req)
            assert resp["ok"] is True
            assert resp["data"]["version"] == __version__
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

    async def test_session_close_all_empty(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            resp = await _send_recv(port, make_request("session_close_all"))
            assert resp["ok"] is True
            assert resp["data"]["closed"] == []
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_session_close_all_with_sessions(self):
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            # Create sessions via ensure
            await server.session_mgr.ensure("s1")
            await server.session_mgr.ensure("s2")
            assert server.session_mgr.count == 2

            resp = await _send_recv(port, make_request("session_close_all"))
            assert resp["ok"] is True
            assert sorted(resp["data"]["closed"]) == ["s1", "s2"]
            assert server.session_mgr.count == 0
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
        # Redirect data dir to tmp (both server and ipc use _data_dir)
        monkeypatch.setattr("maafw_cli.daemon.server._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)

        server = DaemonServer(port=0)
        server.port = await server._bind()
        actual_port = server._server.sockets[0].getsockname()[1]
        server.port = actual_port
        server._write_pid_port_files()

        pid_path = tmp_path / "daemon.pid"
        port_path = tmp_path / "daemon.port"

        assert pid_path.exists()
        assert port_path.exists()
        assert int(pid_path.read_text()) == os.getpid()
        assert int(port_path.read_text()) == actual_port

        server._server.close()
        await server._server.wait_closed()

    async def test_cleanup_removes_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.daemon.server._data_dir", lambda: tmp_path)
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)

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


class TestDaemonServerMessageLimit:
    async def test_oversized_message_dropped(self):
        """Server should drop connection when message exceeds MAX_LINE_LENGTH."""
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            huge_payload = b"x" * (DaemonServer.MAX_LINE_LENGTH + 100) + b"\n"
            writer.write(huge_payload)
            await writer.drain()

            # Server should close the connection
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if line:
                resp = decode(line)
                assert resp["ok"] is False

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


class TestDaemonServerEmptySessionName:
    async def test_session_default_empty_name_rejected(self):
        """session_default with empty name should return error."""
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            resp = await _send_recv(port, make_request("session_default", {"name": ""}))
            assert resp["ok"] is False

            resp = await _send_recv(port, make_request("session_default", {}))
            assert resp["ok"] is False
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_session_close_empty_name_rejected(self):
        """session_close with empty name should return error."""
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            resp = await _send_recv(port, make_request("session_close", {"name": ""}))
            assert resp["ok"] is False
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()


class TestLogSanitization:
    def test_sensitive_keys_redacted(self):
        params = {
            "device": "emu-5554",
            "token": "secret123",
            "api_key": "abc",
            "password": "hunter2",
            "normal_field": "visible",
        }
        sanitized = _sanitize_params(params)
        assert sanitized["device"] == "emu-5554"
        assert sanitized["token"] == "***"
        assert sanitized["api_key"] == "***"
        assert sanitized["password"] == "***"
        assert sanitized["normal_field"] == "visible"

    def test_empty_params(self):
        assert _sanitize_params({}) == {}

    def test_no_sensitive_keys(self):
        params = {"x": 1, "y": 2}
        assert _sanitize_params(params) == {"x": 1, "y": 2}


class TestPortRangeExhaustion:
    """Server should raise RuntimeError when all ports in range are taken."""

    async def test_all_ports_taken(self):
        from maafw_cli.daemon.server import DEFAULT_PORT, PORT_RANGE_END

        # Occupy all ports in range
        occupied = []
        for port in range(DEFAULT_PORT, PORT_RANGE_END):
            try:
                srv = await asyncio.start_server(lambda r, w: None, "127.0.0.1", port)
                occupied.append(srv)
            except OSError:
                pass  # already in use

        try:
            server = DaemonServer()  # no explicit port → tries range
            with pytest.raises(RuntimeError, match="Cannot bind"):
                await server._bind()
        finally:
            for srv in occupied:
                srv.close()
                await srv.wait_closed()


class TestHeartbeat:
    """Tests for server-side heartbeat during long-running requests."""

    async def test_heartbeat_sent_on_slow_request(self):
        """Server sends heartbeat messages when a request takes longer than HEARTBEAT_INTERVAL."""
        import maafw_cli.daemon.server as srv_mod

        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())

        # Patch HEARTBEAT_INTERVAL to a very short value for fast test
        original_interval = srv_mod.HEARTBEAT_INTERVAL
        srv_mod.HEARTBEAT_INTERVAL = 0.2

        # Inject a slow action into the dispatch table
        original_dispatch = server._dispatch

        async def slow_dispatch(action, params, session_name, request):
            if action == "slow_test":
                await asyncio.sleep(0.7)  # >3× heartbeat interval
                return {"done": True}
            return await original_dispatch(action, params, session_name, request)

        server._dispatch = slow_dispatch

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            req = make_request("slow_test")
            writer.write(encode(req))
            await writer.drain()

            # Collect all lines until we get the real response
            heartbeats = []
            final_resp = None
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                msg = decode(line)
                if msg.get("heartbeat"):
                    heartbeats.append(msg)
                else:
                    final_resp = msg
                    break

            assert len(heartbeats) >= 2, f"Expected ≥2 heartbeats, got {len(heartbeats)}"
            assert all("elapsed" in hb for hb in heartbeats)
            assert final_resp["ok"] is True
            assert final_resp["data"]["done"] is True

            writer.close()
            await writer.wait_closed()
        finally:
            srv_mod.HEARTBEAT_INTERVAL = original_interval
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()

    async def test_no_heartbeat_for_fast_request(self):
        """Fast requests should complete without any heartbeat messages."""
        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            req = make_request("ping")
            writer.write(encode(req))
            await writer.drain()

            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            resp = decode(line)
            # Should be the real response, not a heartbeat
            assert "heartbeat" not in resp
            assert resp["ok"] is True
            assert resp["data"]["pong"] is True

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

    async def test_heartbeat_cancelled_on_client_disconnect(self):
        """When client disconnects, heartbeat write fails and task is cancelled."""
        import maafw_cli.daemon.server as srv_mod

        server, port = await _start_server()
        serve_task = asyncio.create_task(server._server.serve_forever())

        original_interval = srv_mod.HEARTBEAT_INTERVAL
        srv_mod.HEARTBEAT_INTERVAL = 0.1

        slow_task_cancelled = asyncio.Event()
        original_dispatch = server._dispatch

        async def slow_dispatch(action, params, session_name, request):
            if action == "slow_disconnect_test":
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    slow_task_cancelled.set()
                    raise
                return {"done": True}
            return await original_dispatch(action, params, session_name, request)

        server._dispatch = slow_dispatch

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            req = make_request("slow_disconnect_test")
            writer.write(encode(req))
            await writer.drain()

            # Wait a bit for the request to start processing, then disconnect
            await asyncio.sleep(0.15)
            writer.close()
            await writer.wait_closed()

            # Give server time to detect the disconnect and cancel
            await asyncio.sleep(0.5)

            # Server should still be alive — verify with a ping
            resp = await _send_recv(port, make_request("ping"))
            assert resp["ok"] is True
        finally:
            srv_mod.HEARTBEAT_INTERVAL = original_interval
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
            server._server.close()
            await server._server.wait_closed()
