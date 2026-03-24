"""
Service-level tests — business logic with MockController, no device needed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from maafw_cli.core.errors import ActionError
from maafw_cli.core.textref import TextRefStore, TextRef
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.interaction import do_click, do_swipe, do_scroll, do_type, do_key
from mock_controller import MockController


def _make_ctx(
    mock: MockController | None = None,
    textrefs_path: Path | None = None,
    session_type: str = "win32",
) -> ServiceContext:
    """Build a ServiceContext backed by a MockController."""
    if mock is None:
        mock = MockController()
    return ServiceContext(
        get_controller=lambda: mock,
        textrefs_path=textrefs_path or Path("/nonexistent"),
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

    def test_click_by_textref(self, tmp_path):
        store = TextRefStore(tmp_path / "textrefs.json")
        store._refs = [TextRef(ref="t1", text="Hello", box=[120, 40, 80, 20], score=0.95)]
        store.save()

        mock = MockController()
        ctx = _make_ctx(mock, textrefs_path=tmp_path / "textrefs.json")
        result = do_click(ctx, target="t1")
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
            do_click(ctx, target="t999")

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
            textrefs_path=Path("/nonexistent"),
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
            textrefs_path=Path("/nonexistent"),
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
