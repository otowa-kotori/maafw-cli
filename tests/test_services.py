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
from maafw_cli.services.interaction import (
    do_click, do_swipe, do_scroll, do_type, do_key,
    do_longpress, do_startapp, do_stopapp, do_shell,
    do_touch_down, do_touch_move, do_touch_up,
    do_key_down, do_key_up, do_mousemove, do_custom_action,
)

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

    def test_click_by_box_target(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_click(ctx, target="10,20,30,40")
        assert result["x"] == 25
        assert result["y"] == 40
        assert mock.clicks == [(25, 40)]


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


# ── longpress ──────────────────────────────────────────────────


class TestLongpressService:
    def test_longpress_coords(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_longpress(ctx, target="200,300", duration=1500)
        assert result["action"] == "longpress"
        assert result["x"] == 200
        assert result["y"] == 300
        assert result["duration"] == 1500
        assert mock.touch_downs == [(200, 300, 0, 1)]
        assert mock.touch_ups == [0]

    def test_longpress_element(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        from maafw_cli.core.element import Element
        ctx.session.element_store._elements = [
            Element(ref="e1", text="Hello", box=[100, 50, 40, 20], score=0.9)
        ]
        result = do_longpress(ctx, target="e1")
        assert result["x"] == 120  # 100 + 40//2
        assert result["y"] == 60   # 50 + 20//2

    def test_longpress_default_duration(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_longpress(ctx, target="100,100")
        assert result["duration"] == 1000

    def test_longpress_fails(self):
        mock = MockController(touch_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Long press failed"):
            do_longpress(ctx, target="100,100")

    def test_longpress_negative_duration(self):
        ctx = _make_ctx()
        with pytest.raises(ActionError, match="Duration must be positive"):
            do_longpress(ctx, target="100,100", duration=-1)


# ── startapp / stopapp ─────────────────────────────────────────


class TestStartappService:
    def test_startapp(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_startapp(ctx, intent="com.example/.Main")
        assert result == {"action": "startapp", "intent": "com.example/.Main"}
        assert mock.start_apps == ["com.example/.Main"]

    def test_startapp_fails(self):
        mock = MockController(startapp_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Start app failed"):
            do_startapp(ctx, intent="com.example/.Main")


class TestStopappService:
    def test_stopapp(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_stopapp(ctx, intent="com.example")
        assert result == {"action": "stopapp", "intent": "com.example"}
        assert mock.stop_apps == ["com.example"]

    def test_stopapp_fails(self):
        mock = MockController(stopapp_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Stop app failed"):
            do_stopapp(ctx, intent="com.example")


# ── shell ──────────────────────────────────────────────────────


class TestShellService:
    def test_shell(self):
        mock = MockController(shell_output="hello world\n")
        ctx = _make_ctx(mock)
        result = do_shell(ctx, cmd="echo hello world")
        assert result["action"] == "shell"
        assert result["output"] == "hello world\n"
        assert result["cmd"] == "echo hello world"
        assert result["timeout"] == 20000
        assert mock.shells == [("echo hello world", 20000)]

    def test_shell_custom_timeout(self):
        mock = MockController(shell_output="ok")
        ctx = _make_ctx(mock)
        result = do_shell(ctx, cmd="ls", timeout=5000)
        assert result["timeout"] == 5000
        assert mock.shells == [("ls", 5000)]

    def test_shell_empty_output(self):
        mock = MockController(shell_output="")
        ctx = _make_ctx(mock)
        result = do_shell(ctx, cmd="true")
        assert result["output"] == ""


# ── touch-down / touch-move / touch-up ─────────────────────────


class TestTouchDownService:
    def test_touch_down_coords(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_touch_down(ctx, target="100,200")
        assert result["action"] == "touch_down"
        assert result["x"] == 100
        assert result["y"] == 200
        assert result["contact"] == 0
        assert result["pressure"] == 1
        assert mock.touch_downs == [(100, 200, 0, 1)]

    def test_touch_down_custom_contact(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_touch_down(ctx, target="50,60", contact=2, pressure=3)
        assert result["contact"] == 2
        assert result["pressure"] == 3
        assert mock.touch_downs == [(50, 60, 2, 3)]

    def test_touch_down_fails(self):
        mock = MockController(touch_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Touch down failed"):
            do_touch_down(ctx, target="100,200")


class TestTouchMoveService:
    def test_touch_move_coords(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_touch_move(ctx, target="300,400")
        assert result["action"] == "touch_move"
        assert result["x"] == 300
        assert result["y"] == 400
        assert mock.touch_moves == [(300, 400, 0, 1)]

    def test_touch_move_fails(self):
        mock = MockController(touch_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Touch move failed"):
            do_touch_move(ctx, target="100,200")


class TestTouchUpService:
    def test_touch_up(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_touch_up(ctx)
        assert result == {"action": "touch_up", "contact": 0}
        assert mock.touch_ups == [0]

    def test_touch_up_custom_contact(self):
        mock = MockController()
        ctx = _make_ctx(mock)
        result = do_touch_up(ctx, contact=2)
        assert result == {"action": "touch_up", "contact": 2}
        assert mock.touch_ups == [2]

    def test_touch_up_fails(self):
        mock = MockController(touch_ok=False)
        ctx = _make_ctx(mock)
        with pytest.raises(ActionError, match="Touch up failed"):
            do_touch_up(ctx)


# ── key-down / key-up ──────────────────────────────────────────


class TestKeyDownService:
    def test_key_down_named(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="win32")
        result = do_key_down(ctx, keycode="shift")
        assert result["action"] == "key_down"
        assert result["keycode"] == 0x10
        assert mock.key_downs == [0x10]

    def test_key_down_integer(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="adb")
        result = do_key_down(ctx, keycode="66")
        assert result["keycode"] == 66
        assert mock.key_downs == [66]

    def test_key_down_unknown(self):
        ctx = _make_ctx(session_type="win32")
        with pytest.raises(ActionError, match="Unknown key"):
            do_key_down(ctx, keycode="nonexistent")

    def test_key_down_fails(self):
        mock = MockController(key_ok=False)
        ctx = _make_ctx(mock, session_type="win32")
        with pytest.raises(ActionError, match="Key down failed"):
            do_key_down(ctx, keycode="shift")


class TestKeyUpService:
    def test_key_up_named(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="win32")
        result = do_key_up(ctx, keycode="shift")
        assert result["action"] == "key_up"
        assert result["keycode"] == 0x10
        assert mock.key_ups == [0x10]

    def test_key_up_unknown(self):
        ctx = _make_ctx(session_type="adb")
        with pytest.raises(ActionError, match="Unknown key"):
            do_key_up(ctx, keycode="nonexistent")

    def test_key_up_fails(self):
        mock = MockController(key_ok=False)
        ctx = _make_ctx(mock, session_type="win32")
        with pytest.raises(ActionError, match="Key up failed"):
            do_key_up(ctx, keycode="ctrl")


# ── custom action ──────────────────────────────────────────────


class TestCustomActionService:
    @patch("maafw_cli.services.interaction.execute_custom_action")
    def test_custom_action_with_element_target(self, mock_execute):
        ctx = _make_ctx()
        ctx.session.element_store._elements = [
            Element(ref="e1", text="Hello", box=[100, 50, 40, 20], score=0.9)
        ]

        result = do_custom_action(ctx, name="ClickTargetCustom", target="e1")

        assert result["action"] == "custom"
        assert result["custom_action"] == "ClickTargetCustom"
        assert result["box"] == [100, 50, 40, 20]
        assert result["target_source"].startswith("ref:e1")
        mock_execute.assert_called_once_with(
            ctx.session,
            "ClickTargetCustom",
            custom_action_param=None,
            target_offset=(0, 0, 0, 0),
            box=(100, 50, 40, 20),
            reco_detail="",
        )

    @patch("maafw_cli.services.interaction.execute_custom_action")
    def test_custom_action_with_box_target_and_json_param(self, mock_execute):
        ctx = _make_ctx()

        result = do_custom_action(
            ctx,
            name="InputTextCustom",
            params=[
                'custom_action_param={"text":"hello"}',
                "target_offset=1,2,3,4",
            ],
            target="10,20,30,40",
        )

        assert result["custom_action_param"] == {"text": "hello"}
        assert result["box"] == [10, 20, 30, 40]
        assert result["target_offset"] == [1, 2, 3, 4]
        mock_execute.assert_called_once_with(
            ctx.session,
            "InputTextCustom",
            custom_action_param={"text": "hello"},
            target_offset=(1, 2, 3, 4),
            box=(10, 20, 30, 40),
            reco_detail="",
        )

    @patch("maafw_cli.services.interaction.execute_custom_action")
    def test_custom_action_raw_json_target(self, mock_execute):
        ctx = _make_ctx()

        result = do_custom_action(
            ctx,
            raw='{"custom_action":"InputTextCustom","custom_action_param":{"text":"hello"},"target":[300,400],"reco_detail":{"from":"test"}}',
        )

        assert result["custom_action"] == "InputTextCustom"
        assert result["box"] == [300, 400, 0, 0]
        assert result["reco_detail"] == '{"from": "test"}'
        mock_execute.assert_called_once_with(
            ctx.session,
            "InputTextCustom",
            custom_action_param={"text": "hello"},
            target_offset=(0, 0, 0, 0),
            box=(300, 400, 0, 0),
            reco_detail='{"from": "test"}',
        )


# ── mousemove ──────────────────────────────────────────────────


class TestMousemoveService:

    def test_mousemove(self):
        mock = MockController()
        ctx = _make_ctx(mock, session_type="win32")
        result = do_mousemove(ctx, dx=100, dy=-50)
        assert result == {"action": "mousemove", "dx": 100, "dy": -50}
        assert mock.relative_moves == [(100, -50)]

    def test_mousemove_rejected_on_adb(self):
        ctx = _make_ctx(session_type="adb")
        with pytest.raises(ActionError, match="Win32"):
            do_mousemove(ctx, dx=10, dy=20)

    def test_mousemove_fails(self):
        mock = MockController(mousemove_ok=False)
        ctx = _make_ctx(mock, session_type="win32")
        with pytest.raises(ActionError, match="Mouse move failed"):
            do_mousemove(ctx, dx=1, dy=1)


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
        assert resolved.box == (300, 400, 0, 0)
        assert resolved.center == (300, 400)


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
        # Import services to populate DISPATCH table
        import maafw_cli.services.vision  # noqa: F401
        import maafw_cli.services.recognition  # noqa: F401
        import maafw_cli.services.connection  # noqa: F401
        import maafw_cli.services.resource  # noqa: F401
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

        with patch("maafw_cli.maafw.controllers.adb.AdbController", return_value=mock_ctrl):
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

        with patch("maafw_cli.maafw.controllers.win32.Win32Controller", return_value=mock_ctrl):
            result = connect_win32(window)

        assert result is None
        mock_ctrl.destroy.assert_called_once()


# ── reco service ────────────────────────────────────────────────


class TestRecoService:
    def test_reco_registered_in_dispatch(self):
        from maafw_cli.services.registry import DISPATCH
        import maafw_cli.services.recognition  # noqa: F401
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


# ── recognition reflection registry ────────────────────────────


class TestRecoRegistry:
    """Test maafw/recognition.py reflection-based registry and build_params."""

    def test_registry_has_all_10_types(self):
        from maafw_cli.maafw.recognition import _REGISTRY
        from maa.pipeline import JRecognitionType

        for member in JRecognitionType:
            assert member.value in _REGISTRY, f"Missing type: {member.value}"
        assert len(_REGISTRY) == len(JRecognitionType)

    def test_registry_maps_to_correct_classes(self):
        from maafw_cli.maafw.recognition import _REGISTRY
        from maa.pipeline import (
            JDirectHit, JTemplateMatch, JFeatureMatch, JColorMatch, JOCR,
            JNeuralNetworkClassify, JNeuralNetworkDetect, JAnd, JOr,
            JCustomRecognition, JRecognitionType,
        )
        assert _REGISTRY["DirectHit"] == (JRecognitionType.DirectHit, JDirectHit)
        assert _REGISTRY["TemplateMatch"] == (JRecognitionType.TemplateMatch, JTemplateMatch)
        assert _REGISTRY["OCR"] == (JRecognitionType.OCR, JOCR)
        assert _REGISTRY["And"] == (JRecognitionType.And, JAnd)
        assert _REGISTRY["Or"] == (JRecognitionType.Or, JOr)
        assert _REGISTRY["Custom"] == (JRecognitionType.Custom, JCustomRecognition)

    def test_build_template_match_from_kv(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("TemplateMatch", {
            "template": "btn.png,icon.png",
            "roi": "0,0,400,300",
            "threshold": "0.8",
            "green_mask": "true",
            "method": "3",
        })
        assert obj.template == ["btn.png", "icon.png"]
        assert obj.roi == (0, 0, 400, 300)
        assert obj.threshold == [0.8]
        assert obj.green_mask is True
        assert obj.method == 3

    def test_build_ocr_from_kv(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("OCR", {
            "expected": "PLAY,START",
            "roi": "10,20,100,50",
            "threshold": "0.5",
            "only_rec": "yes",
        })
        assert obj.expected == ["PLAY", "START"]
        assert obj.roi == (10, 20, 100, 50)
        assert obj.threshold == 0.5
        assert obj.only_rec is True

    def test_build_color_match_from_kv(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("ColorMatch", {
            "lower": "[[200,0,0]]",
            "upper": "[[255,100,100]]",
            "connected": "false",
        })
        assert obj.lower == [[200, 0, 0]]
        assert obj.upper == [[255, 100, 100]]
        assert obj.connected is False

    def test_build_feature_match_from_kv(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("FeatureMatch", {
            "template": "icon.png",
            "ratio": "0.7",
            "count": "6",
        })
        assert obj.template == ["icon.png"]
        assert obj.ratio == 0.7
        assert obj.count == 6

    def test_build_direct_hit_defaults(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("DirectHit", {})
        assert obj.roi == (0, 0, 0, 0)

    def test_build_and_from_raw_json(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("And", {
            "all_of": [
                {"recognition": "OCR", "expected": ["PLAY"]},
                "SomeNodeRef",
            ],
        }, from_string=False)
        assert len(obj.all_of) == 2
        assert obj.all_of[1] == "SomeNodeRef"

    def test_build_or_from_raw_json(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("Or", {
            "any_of": ["NodeA", "NodeB"],
        }, from_string=False)
        assert obj.any_of == ["NodeA", "NodeB"]

    def test_build_custom_recognition(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("Custom", {
            "custom_recognition": "MyCustomReco",
        })
        assert obj.custom_recognition == "MyCustomReco"

    def test_build_custom_recognition_with_json_param(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("Custom", {
            "custom_recognition": "MyCustomReco",
            "custom_recognition_param": '{"expected":"START","threshold":0.8}',
        })
        assert obj.custom_recognition == "MyCustomReco"
        assert obj.custom_recognition_param == {
            "expected": "START",
            "threshold": 0.8,
        }

    def test_build_neural_network_classify(self):

        from maafw_cli.maafw.recognition import build_params
        obj = build_params("NeuralNetworkClassify", {"model": "cls.onnx"})
        assert obj.model == "cls.onnx"

    def test_build_neural_network_detect(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("NeuralNetworkDetect", {"model": "det.onnx"})
        assert obj.model == "det.onnx"

    def test_required_field_missing(self):
        from maafw_cli.core.errors import RecognitionError as RE
        from maafw_cli.maafw.recognition import build_params
        with pytest.raises(RE, match="requires 'template'"):
            build_params("TemplateMatch", {})

    def test_unknown_type(self):
        from maafw_cli.core.errors import RecognitionError as RE
        from maafw_cli.maafw.recognition import build_params
        with pytest.raises(RE, match="Unknown recognition type"):
            build_params("NonExistent", {})

    def test_unknown_fields_ignored(self):
        from maafw_cli.maafw.recognition import build_params
        obj = build_params("OCR", {"unknown_field": "whatever"})
        assert obj.expected == []

    def test_build_params_from_raw_json(self):
        from maafw_cli.maafw.recognition import build_params_from_raw
        import json
        raw = json.dumps({
            "recognition": "TemplateMatch",
            "template": ["btn.png"],
            "threshold": [0.9],
            "roi": [10, 20, 100, 50],
        })
        reco_type, obj = build_params_from_raw(raw)
        assert reco_type == "TemplateMatch"
        assert obj.template == ["btn.png"]
        assert obj.threshold == [0.9]
        assert obj.roi == (10, 20, 100, 50)

    def test_build_params_from_raw_ocr(self):
        from maafw_cli.maafw.recognition import build_params_from_raw
        import json
        raw = json.dumps({
            "recognition": "OCR",
            "expected": ["PLAY"],
            "only_rec": True,
        })
        reco_type, obj = build_params_from_raw(raw)
        assert reco_type == "OCR"
        assert obj.expected == ["PLAY"]
        assert obj.only_rec is True

    def test_build_params_from_raw_invalid_json(self):
        from maafw_cli.core.errors import RecognitionError as RE
        from maafw_cli.maafw.recognition import build_params_from_raw
        with pytest.raises(RE, match="Invalid JSON"):
            build_params_from_raw("not json")

    def test_build_params_from_raw_missing_recognition(self):
        from maafw_cli.core.errors import RecognitionError as RE
        from maafw_cli.maafw.recognition import build_params_from_raw
        with pytest.raises(RE, match="recognition"):
            build_params_from_raw('{"template": ["a.png"]}')


class TestCoerce:
    """Test _coerce type conversion function."""

    def test_int(self):
        from maafw_cli.maafw.recognition import _coerce
        assert _coerce("42", int, from_string=True) == 42
        assert _coerce(42, int) == 42

    def test_float(self):
        from maafw_cli.maafw.recognition import _coerce
        assert _coerce("0.7", float, from_string=True) == 0.7
        assert _coerce(0.7, float) == 0.7

    def test_bool_from_string(self):
        from maafw_cli.maafw.recognition import _coerce
        assert _coerce("true", bool, from_string=True) is True
        assert _coerce("false", bool, from_string=True) is False
        assert _coerce("1", bool, from_string=True) is True
        assert _coerce("yes", bool, from_string=True) is True
        assert _coerce("no", bool, from_string=True) is False

    def test_bool_from_json(self):
        from maafw_cli.maafw.recognition import _coerce
        assert _coerce(True, bool) is True
        assert _coerce(False, bool) is False

    def test_str(self):
        from maafw_cli.maafw.recognition import _coerce
        assert _coerce("hello", str) == "hello"
        assert _coerce(42, str) == "42"

    def test_list_str_from_string(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import List
        result = _coerce("a,b,c", List[str], from_string=True)
        assert result == ["a", "b", "c"]

    def test_list_int_from_string(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import List
        result = _coerce("1,2,3", List[int], from_string=True)
        assert result == [1, 2, 3]

    def test_list_from_json(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import List
        result = _coerce(["a", "b"], List[str])
        assert result == ["a", "b"]

    def test_tuple_from_string(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import Tuple
        result = _coerce("10,20,30,40", Tuple[int, int, int, int], from_string=True)
        assert result == (10, 20, 30, 40)

    def test_tuple_from_json_list(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import Tuple
        result = _coerce([10, 20, 30, 40], Tuple[int, int, int, int])
        assert result == (10, 20, 30, 40)

    def test_any_passthrough(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import Any
        value = {"nested": [1, 2]}
        assert _coerce(value, Any) is value

    def test_list_any_passthrough(self):
        from maafw_cli.maafw.recognition import _coerce
        from typing import List, Any
        value = [{"recognition": "OCR"}, "NodeRef"]
        result = _coerce(value, List[Any])
        assert result is value


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
        with patch("maafw_cli.services.connection.device.init_toolkit"), \
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
