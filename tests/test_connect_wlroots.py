"""
Tests for WlRoots controller — maafw wrapper + service inner + service decorator.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import DeviceConnectionError


# ── maafw wrapper ────────────────────────────────────────────────


class TestConnectWlrootsWrapper:
    def test_success(self):
        from maafw_cli.maafw.controllers.wlroots import connect_wlroots

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True

        with patch("maafw_cli.maafw.controllers.wlroots.WlRootsController", return_value=mock_ctrl):
            result = connect_wlroots("/run/user/1000/wayland-0")

        assert result is mock_ctrl

    def test_failure_returns_none(self):
        from maafw_cli.maafw.controllers.wlroots import connect_wlroots

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False

        with patch("maafw_cli.maafw.controllers.wlroots.WlRootsController", return_value=mock_ctrl):
            result = connect_wlroots("/run/user/1000/wayland-0")

        assert result is None
        mock_ctrl.destroy.assert_called_once()


# ── service inner ────────────────────────────────────────────────


class TestConnectWlrootsInner:
    def test_success(self):
        from maafw_cli.services.connection.wlroots import _connect_wlroots_inner

        mock_ctrl = MagicMock()
        with patch("maafw_cli.services.connection.wlroots.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.wlroots.WlRootsController", return_value=mock_ctrl):
            mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True
            result, controller = _connect_wlroots_inner("/run/user/1000/wayland-0")

        assert result["type"] == "wlroots"
        assert result["wlr_socket_path"] == "/run/user/1000/wayland-0"
        assert controller is mock_ctrl

    def test_failure_raises(self):
        from maafw_cli.services.connection.wlroots import _connect_wlroots_inner

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False

        with patch("maafw_cli.services.connection.wlroots.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.wlroots.WlRootsController", return_value=mock_ctrl):
            with pytest.raises(DeviceConnectionError, match="Failed to connect"):
                _connect_wlroots_inner("/run/user/1000/wayland-0")


# ── service decorator ────────────────────────────────────────────


class TestConnectWlrootsService:
    def test_dispatch_key(self):
        from maafw_cli.services.connection.wlroots import do_connect_wlroots
        assert do_connect_wlroots.dispatch_key == "connect_wlroots"

    def test_needs_session_false(self):
        from maafw_cli.services.connection.wlroots import do_connect_wlroots
        assert do_connect_wlroots.needs_session is False

    def test_service_calls_inner(self):
        from maafw_cli.services.connection.wlroots import do_connect_wlroots

        mock_ctrl = MagicMock()
        inner_result = ({"type": "wlroots", "wlr_socket_path": "/tmp/wl"}, mock_ctrl)

        with patch("maafw_cli.services.connection.wlroots._connect_wlroots_inner", return_value=inner_result):
            result = do_connect_wlroots(wlr_socket_path="/tmp/wl", session_name="test")

        assert result["session"] == "test"
        assert result["type"] == "wlroots"
