"""
Service-level tests — business logic with MockController, no device needed.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import ActionError
from maafw_cli.core.element import ElementStore, Element
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.interaction import do_click, do_swipe, do_scroll, do_type, do_key
from mock_controller import MockController


def _make_ctx(
    mock: MockController | None = None,
    elements_path: Path | None = None,
    session_type: str = "win32",
) -> ServiceContext:
    """Build a ServiceContext backed by a MockController."""
    if mock is None:
        mock = MockController()
    return ServiceContext(
        get_controller=lambda: mock,
        elements_path=elements_path or Path("/nonexistent"),
        session_type=session_type,
    )


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

    def test_click_by_element(self, tmp_path):
        store = ElementStore(tmp_path / "elements.json")
        store._elements = [Element(ref="e1", text="Hello", box=[120, 40, 80, 20], score=0.95)]
        store.save()

        mock = MockController()
        ctx = _make_ctx(mock, elements_path=tmp_path / "elements.json")
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
    def test_controller_cached(self):
        """Controller is created once, then reused."""
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return MockController()

        ctx = ServiceContext(
            get_controller=factory,
            elements_path=Path("/nonexistent"),
            session_type="win32",
        )
        _ = ctx.controller
        _ = ctx.controller
        assert call_count == 1

    def test_invalidate_controller(self):
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return MockController()

        ctx = ServiceContext(
            get_controller=factory,
            elements_path=Path("/nonexistent"),
            session_type="win32",
        )
        _ = ctx.controller
        ctx.invalidate_controller()
        _ = ctx.controller
        assert call_count == 2

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

        with patch("maafw_cli.maafw.win32.Win32Controller", return_value=mock_ctrl):
            result = connect_win32(window)

        assert result is None
        mock_ctrl.destroy.assert_called_once()
