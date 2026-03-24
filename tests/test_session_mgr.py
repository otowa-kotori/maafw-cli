"""Tests for SessionManager — named sessions with MockController."""
from __future__ import annotations

import asyncio

import pytest

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.session import SessionInfo
from maafw_cli.daemon.session_mgr import ManagedSession, SessionManager
from mock_controller import MockController

# Import services to populate DISPATCH table
import maafw_cli.services.interaction  # noqa: F401


def _make_info(type_: str = "adb", device: str = "emu-5554") -> SessionInfo:
    return SessionInfo(type=type_, device=device)


class TestSessionManagerBasics:
    def test_add_and_get(self):
        mgr = SessionManager()
        ctrl = MockController()
        mgr.add("phone", ctrl, _make_info())
        session = mgr.get("phone")
        assert session.name == "phone"
        assert session.controller is ctrl

    def test_first_session_becomes_default(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())
        assert mgr.default_name == "phone"

    def test_get_none_returns_default(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())
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
        mgr.add("phone", MockController(), _make_info(device="emu-5554"))
        mgr.add("tablet", MockController(), _make_info(device="emu-5556"))
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
        mgr.add("phone", MockController(), _make_info())
        assert mgr.count == 1

    def test_session_names(self):
        mgr = SessionManager()
        mgr.add("a", MockController(), _make_info())
        mgr.add("b", MockController(), _make_info())
        assert set(mgr.session_names) == {"a", "b"}


class TestSessionManagerClose:
    def test_close_session(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())
        mgr.close("phone")
        assert mgr.count == 0

    def test_close_nonexistent_raises(self):
        mgr = SessionManager()
        with pytest.raises(KeyError, match="not found"):
            mgr.close("nope")

    def test_close_default_switches(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())
        mgr.add("tablet", MockController(), _make_info())
        assert mgr.default_name == "phone"
        mgr.close("phone")
        # Default switches to remaining session
        assert mgr.default_name == "tablet"

    def test_close_last_session_clears_default(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())
        mgr.close("phone")
        assert mgr.default_name is None

    def test_close_all(self):
        mgr = SessionManager()
        mgr.add("a", MockController(), _make_info())
        mgr.add("b", MockController(), _make_info())
        mgr.close_all()
        assert mgr.count == 0
        assert mgr.default_name is None


class TestSessionManagerDefault:
    def test_set_default(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())
        mgr.add("tablet", MockController(), _make_info())
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
        mgr.add("phone", ctrl1, _make_info(device="old"))
        mgr.add("phone", ctrl2, _make_info(device="new"))
        session = mgr.get("phone")
        assert session.controller is ctrl2
        assert session.session_info.device == "new"
        assert mgr.count == 1


class TestManagedSession:
    def test_make_service_context(self):
        ctrl = MockController()
        info = _make_info(type_="adb", device="emu")
        session = ManagedSession(
            name="phone",
            controller=ctrl,
            session_info=info,
        )
        svc_ctx = session.make_service_context()
        assert svc_ctx.controller is ctrl
        assert svc_ctx.session_type == "adb"
        assert svc_ctx.session_name == "phone"


class TestSessionManagerExecute:
    def test_execute_click(self):
        mgr = SessionManager()
        ctrl = MockController()
        mgr.add("phone", ctrl, _make_info())

        result = asyncio.get_event_loop().run_until_complete(
            mgr.execute("click", {"target": "100,200"}, session_name="phone")
        )
        assert result["action"] == "click"
        assert result["x"] == 100
        assert result["y"] == 200
        assert ctrl.clicks == [(100, 200)]

    def test_execute_unknown_action_raises(self):
        mgr = SessionManager()
        mgr.add("phone", MockController(), _make_info())

        with pytest.raises(ValueError, match="Unknown action"):
            asyncio.get_event_loop().run_until_complete(
                mgr.execute("nonexistent", {}, session_name="phone")
            )

    def test_execute_uses_default_session(self):
        mgr = SessionManager()
        ctrl = MockController()
        mgr.add("phone", ctrl, _make_info())

        result = asyncio.get_event_loop().run_until_complete(
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
            asyncio.get_event_loop().run_until_complete(
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
        result = asyncio.get_event_loop().run_until_complete(
            mgr.execute("_test_global", {"x": 42})
        )
        assert result == {"x": 42}

        # Clean up
        del DISPATCH["_test_global"]
