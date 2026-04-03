"""
Tests for Dbg controller — maafw wrapper + service inner + dbg_type parsing + service decorator.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import DeviceConnectionError


# ── maafw wrapper ────────────────────────────────────────────────


class TestConnectDbgWrapper:
    def test_success(self):
        from maafw_cli.maafw.controllers.dbg import connect_dbg

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True

        with patch("maafw_cli.maafw.controllers.dbg.DbgController", return_value=mock_ctrl):
            result = connect_dbg("/tmp/read", "/tmp/write", 1, {})

        assert result is mock_ctrl

    def test_failure_returns_none(self):
        from maafw_cli.maafw.controllers.dbg import connect_dbg

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False

        with patch("maafw_cli.maafw.controllers.dbg.DbgController", return_value=mock_ctrl):
            result = connect_dbg("/tmp/read", "/tmp/write", 1, {})

        assert result is None
        mock_ctrl.destroy.assert_called_once()

    def test_default_config_none(self):
        from maafw_cli.maafw.controllers.dbg import connect_dbg

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True

        with patch("maafw_cli.maafw.controllers.dbg.DbgController", return_value=mock_ctrl) as mock_cls:
            connect_dbg("/tmp/read", "/tmp/write", 2)

        # config=None → should pass {} to DbgController
        mock_cls.assert_called_once_with("/tmp/read", "/tmp/write", 2, {})


# ── dbg_type parsing ─────────────────────────────────────────────


class TestParseDbgType:
    def test_integer_string(self):
        from maafw_cli.services.connection.dbg import _parse_dbg_type
        assert _parse_dbg_type("1") == 1
        assert _parse_dbg_type("2") == 2

    def test_hex_string(self):
        from maafw_cli.services.connection.dbg import _parse_dbg_type
        assert _parse_dbg_type("0x1") == 1

    def test_name_carousel_image(self):
        from maafw_cli.services.connection.dbg import _parse_dbg_type
        assert _parse_dbg_type("carousel_image") == 1
        assert _parse_dbg_type("CarouselImage") == 1
        assert _parse_dbg_type("carouselimage") == 1

    def test_name_replay_recording(self):
        from maafw_cli.services.connection.dbg import _parse_dbg_type
        assert _parse_dbg_type("replay_recording") == 2
        assert _parse_dbg_type("ReplayRecording") == 2
        assert _parse_dbg_type("replay-recording") == 2

    def test_invalid_name(self):
        from maafw_cli.services.connection.dbg import _parse_dbg_type
        with pytest.raises(DeviceConnectionError, match="Invalid dbg_type"):
            _parse_dbg_type("nonexistent")


# ── service inner ────────────────────────────────────────────────


class TestConnectDbgInner:
    def test_success(self):
        from maafw_cli.services.connection.dbg import _connect_dbg_inner

        mock_ctrl = MagicMock()
        with patch("maafw_cli.services.connection.dbg.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.dbg.DbgController", return_value=mock_ctrl):
            mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True
            result, controller = _connect_dbg_inner("/tmp/read", "/tmp/write", "carousel_image")

        assert result["type"] == "dbg"
        assert result["read_path"] == "/tmp/read"
        assert result["write_path"] == "/tmp/write"
        assert result["dbg_type"] == 1
        assert controller is mock_ctrl

    def test_failure_raises(self):
        from maafw_cli.services.connection.dbg import _connect_dbg_inner

        mock_ctrl = MagicMock()
        mock_ctrl.post_connection.return_value.wait.return_value.succeeded = False

        with patch("maafw_cli.services.connection.dbg.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.dbg.DbgController", return_value=mock_ctrl):
            with pytest.raises(DeviceConnectionError, match="Failed to connect"):
                _connect_dbg_inner("/tmp/read", "/tmp/write")

    def test_with_config_json(self):
        from maafw_cli.services.connection.dbg import _connect_dbg_inner

        mock_ctrl = MagicMock()
        with patch("maafw_cli.services.connection.dbg.init_toolkit"), \
             patch("maafw_cli.maafw.controllers.dbg.DbgController", return_value=mock_ctrl) as mock_cls:
            mock_ctrl.post_connection.return_value.wait.return_value.succeeded = True
            _connect_dbg_inner("/r", "/w", "1", config='{"key": "value"}')

        mock_cls.assert_called_once_with("/r", "/w", 1, {"key": "value"})

    def test_invalid_config_json(self):
        from maafw_cli.services.connection.dbg import _connect_dbg_inner

        with patch("maafw_cli.services.connection.dbg.init_toolkit"):
            with pytest.raises(DeviceConnectionError, match="Invalid --config JSON"):
                _connect_dbg_inner("/r", "/w", config="not json")


# ── service decorator ────────────────────────────────────────────


class TestConnectDbgService:
    def test_dispatch_key(self):
        from maafw_cli.services.connection.dbg import do_connect_dbg
        assert do_connect_dbg.dispatch_key == "connect_dbg"

    def test_needs_session_false(self):
        from maafw_cli.services.connection.dbg import do_connect_dbg
        assert do_connect_dbg.needs_session is False

    def test_service_calls_inner(self):
        from maafw_cli.services.connection.dbg import do_connect_dbg

        mock_ctrl = MagicMock()
        inner_result = ({"type": "dbg", "read_path": "/r", "write_path": "/w", "dbg_type": 1}, mock_ctrl)

        with patch("maafw_cli.services.connection.dbg._connect_dbg_inner", return_value=inner_result):
            result = do_connect_dbg(
                read_path="/r", write_path="/w",
                dbg_type="carousel_image", session_name="test",
            )

        assert result["session"] == "test"
        assert result["type"] == "dbg"
