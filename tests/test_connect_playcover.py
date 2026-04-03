"""
Tests for PlayCover controller — maafw wrapper + service inner + service decorator.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import DeviceConnectionError


# ── maafw wrapper ────────────────────────────────────────────────


class TestConnectPlaycoverWrapper:
    def test_success(self):
        from maafw_cli.maafw.controllers.playcover import connect_playcover

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True

        with patch("maafw_cli.maafw.controllers.playcover.PlayCoverController", return_value=mock_ctrl):
            result = connect_playcover("192.168.1.1", "abc-uuid")

        assert result is mock_ctrl

    def test_failure_returns_none(self):
        from maafw_cli.maafw.controllers.playcover import connect_playcover

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False

        with patch("maafw_cli.maafw.controllers.playcover.PlayCoverController", return_value=mock_ctrl):
            result = connect_playcover("192.168.1.1", "abc-uuid")

        assert result is None
        mock_ctrl.destroy.assert_called_once()


# ── service inner ────────────────────────────────────────────────


class TestConnectPlaycoverInner:
    def test_success(self):
        from maafw_cli.services.connection.playcover import _connect_playcover_inner

        mock_ctrl = MagicMock()
        with patch("maafw_cli.services.connection.playcover.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.playcover.PlayCoverController", return_value=mock_ctrl):
            mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True
            result, controller = _connect_playcover_inner("10.0.0.1", "uuid-123")

        assert result["type"] == "playcover"
        assert result["address"] == "10.0.0.1"
        assert result["uuid"] == "uuid-123"
        assert controller is mock_ctrl

    def test_failure_raises(self):
        from maafw_cli.services.connection.playcover import _connect_playcover_inner

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False

        with patch("maafw_cli.services.connection.playcover.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.playcover.PlayCoverController", return_value=mock_ctrl):
            with pytest.raises(DeviceConnectionError, match="Failed to connect"):
                _connect_playcover_inner("10.0.0.1", "uuid-123")


# ── service decorator ────────────────────────────────────────────


class TestConnectPlaycoverService:
    def test_dispatch_key(self):
        from maafw_cli.services.connection.playcover import do_connect_playcover
        assert do_connect_playcover.dispatch_key == "connect_playcover"

    def test_needs_session_false(self):
        from maafw_cli.services.connection.playcover import do_connect_playcover
        assert do_connect_playcover.needs_session is False

    def test_service_calls_inner(self):
        from maafw_cli.services.connection.playcover import do_connect_playcover

        mock_ctrl = MagicMock()
        inner_result = ({"type": "playcover", "address": "a", "uuid": "b"}, mock_ctrl)

        with patch("maafw_cli.services.connection.playcover._connect_playcover_inner", return_value=inner_result):
            result = do_connect_playcover(address="a", uuid="b", session_name="test")

        assert result["session"] == "test"
        assert result["type"] == "playcover"
