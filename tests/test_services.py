"""
Service-level tests — business logic with MockController, no device needed.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import ActionError
from maafw_cli.core.element import ElementStore, Element
from maafw_cli.core.session import Session
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.interaction import do_click, do_swipe, do_scroll, do_type, do_key
from mock_controller import MockController


def _make_ctx(
    mock: MockController | None = None,
    session_type: str = "win32",
) -> ServiceContext:
    """Build a ServiceContext backed by a MockController."""
    if mock is None:
        mock = MockController()
    session = Session(name="test")
    session.attach(mock, session_type, "test-device")
    return ServiceContext(session)


# ── click ────────────────────────────────────────────────────────


class TestClickService:
    def test_click_by_coords(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_click(ctx, target="100,200")
        assert result["action"] == "click"
        assert result["x"] == 100
        assert result["y"] == 200
        assert mock.clicks == [(100, 200)]

    def test_click_by_element(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        # Pre-populate element store
        ctx.session.element_store._elements = [
            Element(ref="e1", text="Hello", box=[120, 40, 80, 20], score=0.95)
        ]
        result = do_click(ctx, target="e1")
        assert result["x"] == 160  # 120 + 80//2
        assert result["y"] == 50   # 40 + 20//2
        assert mock.clicks == [(160, 50)]

    def test_click_invalid_target(self):
        ctx = _make_ctx()
        with pytest.raises(ActionError, match="Cannot parse"):
            do_click(ctx, target="!!!invalid")

    def test_click_unknown_ref(self):
        ctx = _make_ctx()
        with pytest.raises(ActionError, match="Unknown reference"):
            do_click(ctx, target="e999")

    def test_click_fails(self):
        mock = MockController(click_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Click failed"):
            do_click(ctx, target="100,200")


# ── swipe ────────────────────────────────────────────────────────


class TestSwipeService:
    def test_swipe_by_coords(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_swipe(ctx, from_target="100,800", to_target="100,200", duration=500)
        assert result["action"] == "swipe"
        assert result["x1"] == 100
        assert result["y1"] == 800
        assert result["x2"] == 100
        assert result["y2"] == 200
        assert result["duration"] == 500
        assert mock.swipes == [(100, 800, 100, 200, 500)]

    def test_swipe_default_duration(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_swipe(ctx, from_target="0,0", to_target="100,100")
        assert result["duration"] == 300

    def test_swipe_fails(self):
        mock = MockController(swipe_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Swipe failed"):
            do_swipe(ctx, from_target="0,0", to_target="100,100")

    def test_swipe_negative_duration(self):
        ctx = _make_ctx()
        with pytest.raises(ActionError, match="Duration must be positive"):
            do_swipe(ctx, from_target="0,0", to_target="100,100", duration=-1)

    def test_swipe_zero_duration(self):
        ctx = _make_ctx()
        with pytest.raises(ActionError, match="Duration must be positive"):
            do_swipe(ctx, from_target="0,0", to_target="100,100", duration=0)


# ── scroll ───────────────────────────────────────────────────────


class TestScrollService:
    def test_scroll(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_scroll(ctx, dx=0, dy=-360)
        assert result == {"action": "scroll", "dx": 0, "dy": -360}
        assert mock.scrolls == [(0, -360)]

    def test_scroll_fails(self):
        mock = MockController(scroll_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Scroll failed"):
            do_scroll(ctx, dx=0, dy=120)

    def test_scroll_rejected_on_adb(self):
        """Scroll should reject non-Win32 sessions."""
        ctx = _make_ctx(session_type="adb")
        with pytest.raises(ActionError, match="Win32"):
            do_scroll(ctx, dx=0, dy=120)


# ── type ─────────────────────────────────────────────────────────


class TestTypeService:
    def test_type(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_type(ctx, text="Hello World")
        assert result == {"action": "type", "text": "Hello World"}
        assert mock.texts == ["Hello World"]

    def test_type_fails(self):
        mock = MockController(type_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Type failed"):
            do_type(ctx, text="test")


# ── key ──────────────────────────────────────────────────────────


class TestKeyService:
    def test_key_win32_enter(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="win32")
        result = do_key(ctx, keycode="enter")
        assert result["keycode"] == 0x0D
        assert mock.keys == [0x0D]

    def test_key_adb_enter(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="adb")
        result = do_key(ctx, keycode="enter")
        assert result["keycode"] == 66
        assert result["session_type"] == "adb"
        assert mock.keys == [66]

    def test_key_adb_back(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="adb")
        result = do_key(ctx, keycode="back")
        assert result["keycode"] == 4

    def test_key_raw_int(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="adb")
        result = do_key(ctx, keycode="66")
        assert result["keycode"] == 66

    def test_key_hex(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="win32")
        result = do_key(ctx, keycode="0x0D")
        assert result["keycode"] == 0x0D

    def test_key_unknown(self):
        ctx = _make_ctx(session_type="win32")
        with pytest.raises(ActionError, match="Unknown key"):
            do_key(ctx, keycode="nonexistent")

    def test_key_fails(self):
        mock = MockController(key_ok=False)
        ctx = _make_ctx(mock, session_type="win32")
        with pytest.raises(ActionError, match="Key press failed"):
            do_key(ctx, keycode="enter")


# ── ServiceContext ───────────────────────────────────────────────


class TestServiceContext:
    def test_controller_from_session(self):
        """Controller comes from the session."""
        mock = MockController()
        session = Session(name="test")
        session.attach(mock, "win32", "test-device")
        ctx = ServiceContext(session)
        assert ctx.controller is mock
        # Accessing again returns the same
        assert ctx.controller is mock

    def test_resolve_target_coords(self):
        ctx = _make_ctx()
        resolved = ctx.resolve_target("300,400")
        assert resolved.x == 300
        assert resolved.y == 400

    def test_resolve_target_invalid(self):
        ctx = _make_ctx()
        with pytest.raises(ActionError):
            ctx.resolve_target("???")


# ── ROI parsing ──────────────────────────────────────────────────


class TestRoiParsing:
    def test_parse_roi_valid(self):
        from maafw_cli.services.vision import _parse_roi
        assert _parse_roi("100,200,300,400") == (100, 200, 300, 400)

    def test_parse_roi_none(self):
        from maafw_cli.services.vision import _parse_roi
        assert _parse_roi(None) is None

    def test_parse_roi_spaces(self):
        from maafw_cli.services.vision import _parse_roi
        assert _parse_roi("100, 200, 300, 400") == (100, 200, 300, 400)

    def test_parse_roi_invalid_count(self):
        from maafw_cli.services.vision import _parse_roi
        with pytest.raises(ActionError, match="Invalid ROI"):
            _parse_roi("100,200")

    def test_parse_roi_non_int(self):
        from maafw_cli.services.vision import _parse_roi
        with pytest.raises(ActionError, match="integers"):
            _parse_roi("a,b,c,d")


# ── resource ─────────────────────────────────────────────────────


class TestResourceService:
    def test_resource_status(self):
        from maafw_cli.services.resource import do_resource_status
        result = do_resource_status()
        assert "ocr_model" in result
        assert "ocr_path" in result
        assert isinstance(result["ocr_model"], bool)


# ── registry decorator ─────────────────────────────────────────────


class TestServiceDecorator:
    """Test @service decorator metadata attachment."""

    def test_dispatch_key_attached(self):
        from maafw_cli.services.interaction import do_click
        assert do_click.dispatch_key == "click"

    def test_needs_session_default_true(self):
        from maafw_cli.services.interaction import do_click
        assert do_click.needs_session is True

    def test_needs_session_false(self):
        from maafw_cli.services.connection import do_device_list
        assert do_device_list.needs_session is False

    def test_connect_services_no_session(self):
        from maafw_cli.services.connection import do_connect_adb, do_connect_win32
        assert do_connect_adb.needs_session is False
        assert do_connect_win32.needs_session is False

    def test_resource_services_no_session(self):
        from maafw_cli.services.resource import do_download_ocr, do_resource_status
        assert do_download_ocr.needs_session is False
        assert do_resource_status.needs_session is False

    def test_human_fmt_attached(self):
        from maafw_cli.services.interaction import do_click
        assert callable(do_click.human_fmt)

    def test_dispatch_table_populated(self):
        from maafw_cli.services.registry import DISPATCH
        # Ensure key services are registered
        assert "click" in DISPATCH
        assert "ocr" in DISPATCH
        assert "reco" in DISPATCH
        assert "device_list" in DISPATCH
        assert "connect_adb" in DISPATCH
        assert "resource_status" in DISPATCH


# ── controller destroy on connection failure ──────────────────────


class TestControllerDestroyOnFailure:
    def test_adb_destroy_on_connect_failure(self):
        """connect_adb should call ctrl.destroy() when connection fails."""
        from maafw_cli.maafw.adb import AdbDeviceInfo, connect_adb

        device = AdbDeviceInfo(
            name="test", adb_path="/usr/bin/adb",
            address="127.0.0.1:5555",
            screencap_methods=1, input_methods=1, config={},
        )

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False
        mock_ctrl.destroy = MagicMock()
        mock_ctrl.set_screenshot_target_short_side = MagicMock()

        with patch("maafw_cli.maafw.adb.AdbController", return_value=mock_ctrl):
            result = connect_adb(device)

        assert result is None
        mock_ctrl.destroy.assert_called_once()

    def test_win32_destroy_on_connect_failure(self):
        """connect_win32 should call ctrl.destroy() when connection fails."""
        from maafw_cli.maafw.win32 import Win32WindowInfo, connect_win32

        window = Win32WindowInfo(hwnd=12345, class_name="Test", window_name="Test Window")

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False
        mock_ctrl.destroy = MagicMock()
        mock_ctrl.set_screenshot_use_raw_size = MagicMock()

        with patch("maafw_cli.maafw.win32.Win32Controller", return_value=mock_ctrl):
            result = connect_win32(window)

        assert result is None
        mock_ctrl.destroy.assert_called_once()


# ── reco service ────────────────────────────────────────────────


class TestRecoService:
    def test_reco_registered_in_dispatch(self):
        from maafw_cli.services.registry import DISPATCH
        assert "reco" in DISPATCH

    def test_reco_needs_session(self):
        from maafw_cli.services.recognition import do_reco
        assert do_reco.needs_session is True

    def test_reco_dispatch_key(self):
        from maafw_cli.services.recognition import do_reco
        assert do_reco.dispatch_key == "reco"


class TestRecoParamsParsing:
    """Test services/recognition.py parameter parsing."""

    def test_parse_kv_pairs(self):
        from maafw_cli.services.recognition import _parse_kv_params
        result = _parse_kv_params("template=button.png roi=0,0,400,200 threshold=0.8")
        assert result == {
            "template": "button.png",
            "roi": "0,0,400,200",
            "threshold": "0.8",
        }

    def test_parse_empty_params(self):
        from maafw_cli.services.recognition import _parse_kv_params
        assert _parse_kv_params(None) == {}
        assert _parse_kv_params("") == {}

    def test_parse_ignores_non_kv(self):
        from maafw_cli.services.recognition import _parse_kv_params
        result = _parse_kv_params("template=a.png garbage roi=0,0,1,1")
        assert result == {"template": "a.png", "roi": "0,0,1,1"}


# ── screenshot size option ──────────────────────────────────────


class TestSizeOption:
    """Test core/screenshot.py parse_size_option and apply_size_option."""

    def test_parse_short(self):
        from maafw_cli.core.screenshot import parse_size_option
        assert parse_size_option("short:720") == ("short", 720)

    def test_parse_long(self):
        from maafw_cli.core.screenshot import parse_size_option
        assert parse_size_option("long:1920") == ("long", 1920)

    def test_parse_raw(self):
        from maafw_cli.core.screenshot import parse_size_option
        assert parse_size_option("raw") == ("raw", None)

    def test_parse_raw_case_insensitive(self):
        from maafw_cli.core.screenshot import parse_size_option
        assert parse_size_option("RAW") == ("raw", None)

    def test_parse_short_case_insensitive(self):
        from maafw_cli.core.screenshot import parse_size_option
        assert parse_size_option("Short:1080") == ("short", 1080)

    def test_parse_invalid_format(self):
        from maafw_cli.core.screenshot import parse_size_option
        with pytest.raises(ValueError, match="Invalid --size format"):
            parse_size_option("invalid")

    def test_parse_invalid_value(self):
        from maafw_cli.core.screenshot import parse_size_option
        with pytest.raises(ValueError, match="expected an integer"):
            parse_size_option("short:abc")

    def test_parse_zero_value(self):
        from maafw_cli.core.screenshot import parse_size_option
        with pytest.raises(ValueError, match="positive"):
            parse_size_option("short:0")

    def test_parse_negative_value(self):
        from maafw_cli.core.screenshot import parse_size_option
        with pytest.raises(ValueError, match="positive"):
            parse_size_option("long:-100")

    def test_apply_short(self):
        from maafw_cli.core.screenshot import apply_size_option
        ctrl = MagicMock()
        apply_size_option(ctrl, "short:720")
        ctrl.set_screenshot_target_short_side.assert_called_once_with(720)

    def test_apply_long(self):
        from maafw_cli.core.screenshot import apply_size_option
        ctrl = MagicMock()
        apply_size_option(ctrl, "long:1920")
        ctrl.set_screenshot_target_long_side.assert_called_once_with(1920)

    def test_apply_raw(self):
        from maafw_cli.core.screenshot import apply_size_option
        ctrl = MagicMock()
        apply_size_option(ctrl, "raw")
        ctrl.set_screenshot_use_raw_size.assert_called_once_with(True)


# ── LocalExecutor ─────────────────────────────────────────────


class TestLocalExecutor:
    """Test in-process service execution without daemon."""

    def _make_executor(self):
        from maafw_cli.core.local_executor import LocalExecutor
        return LocalExecutor()

    def test_session_list_empty(self):
        ex = self._make_executor()
        result = ex.execute("session_list", {})
        assert result == {"sessions": []}

    def test_ping(self):
        ex = self._make_executor()
        result = ex.execute("ping", {})
        assert result["pong"] is True
        assert result["mode"] == "local"

    def test_shutdown_noop(self):
        ex = self._make_executor()
        result = ex.execute("shutdown", {})
        assert "local" in result["message"].lower()

    def test_click_via_dispatch(self):
        """Regular service dispatch through LocalExecutor."""
        from maafw_cli.core.local_executor import LocalExecutor

        ex = LocalExecutor()
        # Create a session manually and attach a mock controller
        mock = MockController()
        session = Session(name="test")
        session.attach(mock, "win32", "test-device")
        ex._sessions["test"] = session
        ex._default = "test"

        result = ex.execute("click", {"target": "100,200"})
        assert result["action"] == "click"
        assert result["x"] == 100
        assert result["y"] == 200
        assert mock.clicks == [(100, 200)]

    def test_no_session_service(self):
        """Session-less services work without any session."""
        ex = self._make_executor()
        # device_list is needs_session=False; will call init_toolkit()
        # which may fail without MaaFW installed, so we mock it
        with patch("maafw_cli.services.connection.init_toolkit"), \
             patch("maafw_cli.maafw.adb.find_adb_devices", return_value=[]):
            result = ex.execute("device_list", {"adb": True, "win32": False})
        assert result == {"adb": []}

    def test_session_default(self):
        ex = self._make_executor()
        # Create two sessions
        ex._sessions["a"] = Session(name="a")
        ex._sessions["b"] = Session(name="b")
        ex._default = "a"

        result = ex.execute("session_default", {"name": "b"})
        assert result == {"default": "b"}
        assert ex._default == "b"

    def test_session_close(self):
        ex = self._make_executor()
        session = Session(name="temp")
        ex._sessions["temp"] = session
        ex._default = "temp"

        result = ex.execute("session_close", {"name": "temp"})
        assert result == {"closed": "temp"}
        assert "temp" not in ex._sessions

    def test_close_all(self):
        ex = self._make_executor()
        mock = MockController()
        session = Session(name="test")
        session.attach(mock, "win32", "test")
        ex._sessions["test"] = session
        ex._default = "test"

        ex.close_all()
        assert len(ex._sessions) == 0

    def test_unknown_action(self):
        ex = self._make_executor()
        with pytest.raises(ValueError, match="Unknown action"):
            ex.execute("nonexistent_action", {})
