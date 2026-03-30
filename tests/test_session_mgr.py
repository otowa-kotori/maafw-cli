"""Tests for SessionManager — named sessions with MockController."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.session import Session
from maafw_cli.daemon.session_mgr import SessionManager
from mock_controller import MockController

# Import services to populate DISPATCH table
import maafw_cli.services.interaction  # noqa: F401


def _run(coro):
    """Helper to run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSessionManagerBasics:
    def test_add_and_get(self):
        mgr = SessionManager()
        ctrl = MockController()
        _run(mgr.add("phone", ctrl, "adb", "emu-5554"))
        session = mgr.get("phone")
        assert session.name == "phone"
        assert session.controller is ctrl

    def test_first_session_becomes_default(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        assert mgr.default_name == "phone"

    def test_get_none_returns_default(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        session = mgr.get(None)
        assert session.name == "phone"

    def test_get_nonexistent_raises(self):
        mgr = SessionManager()
        with pytest.raises(DeviceConnectionError, match="No active session"):
            mgr.get("nope")

    def test_get_none_no_sessions_raises(self):
        mgr = SessionManager()
        with pytest.raises(DeviceConnectionError, match="no default"):
            mgr.get(None)

    def test_list_sessions(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        _run(mgr.add("tablet", MockController(), "adb", "emu-5556"))
        result = mgr.list_sessions()
        assert len(result) == 2
        names = {s["name"] for s in result}
        assert names == {"phone", "tablet"}
        # First added is default
        default_items = [s for s in result if s["is_default"]]
        assert len(default_items) == 1
        assert default_items[0]["name"] == "phone"

    def test_count(self):
        mgr = SessionManager()
        assert mgr.count == 0
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        assert mgr.count == 1

    def test_session_names(self):
        mgr = SessionManager()
        _run(mgr.add("a", MockController(), "adb", "emu"))
        _run(mgr.add("b", MockController(), "adb", "emu"))
        assert set(mgr.session_names) == {"a", "b"}


class TestSessionManagerClose:
    def test_close_session(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        _run(mgr.close("phone"))
        assert mgr.count == 0

    def test_close_nonexistent_raises(self):
        mgr = SessionManager()
        with pytest.raises(KeyError, match="not found"):
            _run(mgr.close("nope"))

    def test_close_default_switches(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        _run(mgr.add("tablet", MockController(), "adb", "emu-5556"))
        assert mgr.default_name == "phone"
        _run(mgr.close("phone"))
        # Default switches to remaining session
        assert mgr.default_name == "tablet"

    def test_close_last_session_clears_default(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))
        _run(mgr.close("phone"))
        assert mgr.default_name is None

    def test_close_all(self):
        mgr = SessionManager()
        _run(mgr.add("a", MockController(), "adb", "emu"))
        _run(mgr.add("b", MockController(), "adb", "emu"))
        _run(mgr.close_all())
        assert mgr.count == 0
        assert mgr.default_name is None


class TestSessionManagerDefault:
    def test_set_default(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu"))
        _run(mgr.add("tablet", MockController(), "adb", "emu"))
        mgr.set_default("tablet")
        assert mgr.default_name == "tablet"

    def test_set_default_nonexistent_raises(self):
        mgr = SessionManager()
        with pytest.raises(KeyError, match="not found"):
            mgr.set_default("nope")


class TestSessionManagerReplace:
    def test_add_duplicate_name_replaces(self):
        mgr = SessionManager()
        ctrl1 = MockController()
        ctrl2 = MockController()
        _run(mgr.add("phone", ctrl1, "adb", "old"))
        _run(mgr.add("phone", ctrl2, "adb", "new"))
        session = mgr.get("phone")
        assert session.controller is ctrl2
        assert session.device == "new"
        assert mgr.count == 1


class TestSessionServiceContext:
    def test_make_service_context(self):
        ctrl = MockController()
        session = Session(name="phone")
        session.attach(ctrl, "adb", "emu")
        from maafw_cli.services.context import ServiceContext
        svc_ctx = ServiceContext(session)
        assert svc_ctx.controller is ctrl
        assert svc_ctx.session_type == "adb"
        assert svc_ctx.session_name == "phone"


class TestSessionManagerExecute:
    def test_execute_click(self):
        mgr = SessionManager()
        ctrl = MockController()
        _run(mgr.add("phone", ctrl, "adb", "emu-5554"))

        result = _run(
            mgr.execute("click", {"target": "100,200"}, session_name="phone")
        )
        assert result["action"] == "click"
        assert result["x"] == 100
        assert result["y"] == 200
        assert ctrl.clicks == [(100, 200)]

    def test_execute_unknown_action_raises(self):
        mgr = SessionManager()
        _run(mgr.add("phone", MockController(), "adb", "emu-5554"))

        with pytest.raises(ValueError, match="Unknown action"):
            _run(
                mgr.execute("nonexistent", {}, session_name="phone")
            )

    def test_execute_uses_default_session(self):
        mgr = SessionManager()
        ctrl = MockController()
        _run(mgr.add("phone", ctrl, "adb", "emu-5554"))

        result = _run(
            mgr.execute("click", {"target": "50,60"})
        )
        assert result["action"] == "click"
        assert ctrl.clicks == [(50, 60)]


class TestSessionManagerConnectionError:
    """Verify that session_mgr raises DeviceConnectionError (not builtin ConnectionError)."""

    def test_error_type_is_maafw(self):
        """The raised error must be our custom DeviceConnectionError with exit_code=3."""
        mgr = SessionManager()
        with pytest.raises(DeviceConnectionError) as exc_info:
            mgr.get("missing")
        assert exc_info.value.exit_code == 3

    def test_error_is_not_builtin(self):
        """Must NOT be the builtin ConnectionError (which is an OSError)."""
        mgr = SessionManager()
        with pytest.raises(DeviceConnectionError):
            mgr.get("missing")
        # Verify it's NOT an OSError (builtin ConnectionError is)
        try:
            mgr.get("missing2")
        except DeviceConnectionError as e:
            assert not isinstance(e, OSError)

    def test_execute_no_session_raises_maafw(self):
        """execute() on empty manager should raise DeviceConnectionError."""
        mgr = SessionManager()
        # Populate DISPATCH with at least one action
        import maafw_cli.services.interaction  # noqa: F401
        with pytest.raises(DeviceConnectionError):
            _run(
                mgr.execute("click", {"target": "1,2"})
            )


class TestSessionManagerNeedsSession:
    """Verify that needs_session=False services can run without a session."""

    def test_execute_no_session_service(self):
        """Services with needs_session=False should run even with no sessions."""
        from maafw_cli.services.registry import DISPATCH, service

        # Register a test service
        @service(name="_test_global", needs_session=False)
        def _test_global_fn(x: int = 1) -> dict:
            return {"x": x}

        mgr = SessionManager()
        result = _run(
            mgr.execute("_test_global", {"x": 42})
        )
        assert result == {"x": 42}

        # Clean up
        del DISPATCH["_test_global"]


class TestSessionManagerConcurrency:
    """Verify asyncio.Lock protects _sessions dict under concurrent access."""

    def test_concurrent_adds_safe(self):
        mgr = SessionManager()

        async def run():
            await asyncio.gather(*[
                mgr.add(f"s{i}", MockController(), "adb", "test")
                for i in range(20)
            ])

        _run(run())
        assert mgr.count == 20

    def test_concurrent_add_and_close(self):
        mgr = SessionManager()

        async def run():
            for i in range(5):
                await mgr.add(f"s{i}", MockController(), "adb", "test")

            tasks = []
            for i in range(5):
                tasks.append(mgr.close(f"s{i}"))
                tasks.append(mgr.add(f"new{i}", MockController(), "adb", "test"))
            await asyncio.gather(*tasks, return_exceptions=True)

        _run(run())
        # Should not have crashed


class TestSessionManagerDestroyInThread:
    """Verify controller.destroy() is called via asyncio.to_thread."""

    def test_destroy_called_on_close(self):
        mgr = SessionManager()
        ctrl = MockController()
        ctrl.destroy = MagicMock()

        _run(mgr.add("test", ctrl, "adb", "test"))
        _run(mgr.close("test"))

        ctrl.destroy.assert_called_once()


class TestSessionDisconnectionDetection:
    """Verify is_connected() and list_sessions() detect device disconnection."""

    def test_is_connected_true(self):
        """Session with a live controller reports connected."""
        session = Session(name="test")
        ctrl = MockController(connected=True)
        session.attach(ctrl, "win32", "TestWindow")
        assert session.is_connected() is True

    def test_is_connected_false_when_disconnected(self):
        """Session with disconnected controller reports not connected."""
        session = Session(name="test")
        ctrl = MockController(connected=False)
        session.attach(ctrl, "win32", "TestWindow")
        assert session.is_connected() is False

    def test_is_connected_false_when_no_controller(self):
        """Session without a controller reports not connected."""
        session = Session(name="test")
        assert session.is_connected() is False

    def test_controller_property_raises_on_disconnect(self):
        """Accessing controller when device disconnected raises DeviceConnectionError."""
        session = Session(name="test")
        ctrl = MockController(connected=False)
        session.attach(ctrl, "win32", "TestWindow")
        with pytest.raises(DeviceConnectionError, match="disconnected"):
            _ = session.controller

    def test_list_sessions_shows_disconnected(self):
        """list_sessions() reflects actual device connectivity."""
        mgr = SessionManager()
        ctrl_alive = MockController(connected=True)
        ctrl_dead = MockController(connected=False)

        _run(mgr.add("alive", ctrl_alive, "win32", "Window1"))
        _run(mgr.add("dead", ctrl_dead, "win32", "Window2"))

        sessions = mgr.list_sessions()
        by_name = {s["name"]: s for s in sessions}
        assert by_name["alive"]["connected"] is True
        assert by_name["dead"]["connected"] is False

    def test_is_connected_handles_exception(self):
        """is_connected() returns False if controller.connected throws."""
        session = Session(name="test")
        ctrl = MockController()
        # Simulate controller.connected raising an exception
        type(ctrl).connected = property(lambda self: (_ for _ in ()).throw(RuntimeError("dead")))
        session.attach(ctrl, "win32", "TestWindow")
        assert session.is_connected() is False
