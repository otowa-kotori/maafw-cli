"""Tests for reconnect — mock session + devices, no real hardware."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.session import SessionInfo


def _make_session(**kwargs) -> SessionInfo:
    defaults = dict(
        type="adb", device="emu-5554", adb_path="/usr/bin/adb",
        address="127.0.0.1:5554", screencap_methods=0, input_methods=0,
        config={}, screenshot_short_side=720, window_name="", name="",
    )
    defaults.update(kwargs)
    return SessionInfo(**defaults)


def _make_adb_device(name="emu-5554", address="127.0.0.1:5554"):
    d = MagicMock()
    d.name = name
    d.address = address
    d.adb_path = "/usr/bin/adb"
    d.screencap_methods = 0
    d.input_methods = 0
    d.config = {}
    return d


def _make_win32_window(window_name="TestApp", hwnd=0x1234, class_name="TestClass"):
    w = MagicMock()
    w.window_name = window_name
    w.hwnd = hwnd
    w.class_name = class_name
    return w


# ── no session ───────────────────────────────────────────────────


class TestReconnectNoSession:
    def test_no_session_raises(self):
        with patch("maafw_cli.core.reconnect.load_session", return_value=None):
            with pytest.raises(DeviceConnectionError, match="No active session"):
                from maafw_cli.core.reconnect import reconnect
                reconnect()

    def test_unsupported_session_type(self):
        session = _make_session(type="bluetooth")
        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"):
            with pytest.raises(DeviceConnectionError, match="Unsupported session type"):
                from maafw_cli.core.reconnect import reconnect
                reconnect()


# ── ADB reconnect ────────────────────────────────────────────────


class TestReconnectAdb:
    def test_adb_success(self):
        session = _make_session(type="adb", device="emu-5554", address="127.0.0.1:5554")
        device = _make_adb_device()
        mock_ctrl = MagicMock()

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"), \
             patch("maafw_cli.maafw.adb.find_adb_devices", return_value=[device]), \
             patch("maafw_cli.maafw.adb.connect_adb", return_value=mock_ctrl):
            from maafw_cli.core.reconnect import reconnect
            result = reconnect()
            assert result is mock_ctrl

    def test_adb_device_not_found(self):
        session = _make_session(type="adb", device="missing-device")

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"), \
             patch("maafw_cli.maafw.adb.find_adb_devices", return_value=[]):
            with pytest.raises(DeviceConnectionError, match="no longer available"):
                from maafw_cli.core.reconnect import reconnect
                reconnect()

    def test_adb_connect_fails(self):
        session = _make_session(type="adb", device="emu-5554")
        device = _make_adb_device()

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"), \
             patch("maafw_cli.maafw.adb.find_adb_devices", return_value=[device]), \
             patch("maafw_cli.maafw.adb.connect_adb", return_value=None):
            with pytest.raises(DeviceConnectionError, match="Failed to reconnect"):
                from maafw_cli.core.reconnect import reconnect
                reconnect()

    def test_adb_match_by_address(self):
        """Device matched by address when name differs."""
        session = _make_session(type="adb", device="old-name", address="127.0.0.1:5554")
        device = _make_adb_device(name="new-name", address="127.0.0.1:5554")
        mock_ctrl = MagicMock()

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"), \
             patch("maafw_cli.maafw.adb.find_adb_devices", return_value=[device]), \
             patch("maafw_cli.maafw.adb.connect_adb", return_value=mock_ctrl):
            from maafw_cli.core.reconnect import reconnect
            result = reconnect()
            assert result is mock_ctrl


# ── Win32 reconnect ──────────────────────────────────────────────


class TestReconnectWin32:
    def test_win32_success(self):
        """Reconnect by saved HWND — no window discovery needed."""
        session = _make_session(type="win32", window_name="TestApp",
                                address="0x1234",
                                screencap_methods=2, input_methods=4)
        mock_ctrl = MagicMock()

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"), \
             patch("maafw_cli.maafw.win32.connect_win32", return_value=mock_ctrl) as mock_connect:
            from maafw_cli.core.reconnect import reconnect
            result = reconnect()
            assert result is mock_ctrl
            # Verify it used the HWND from session, not window discovery
            called_window = mock_connect.call_args[0][0]
            assert called_window.hwnd == 0x1234

    def test_win32_connect_fails(self):
        """When the saved HWND is no longer valid (window closed)."""
        session = _make_session(type="win32", window_name="TestApp",
                                address="0x1234",
                                screencap_methods=2, input_methods=4)

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"), \
             patch("maafw_cli.maafw.win32.connect_win32", return_value=None):
            with pytest.raises(DeviceConnectionError, match="Failed to reconnect"):
                from maafw_cli.core.reconnect import reconnect
                reconnect()

    def test_win32_invalid_hwnd(self):
        """Invalid saved hwnd string should raise a clear error."""
        session = _make_session(type="win32", window_name="TestApp",
                                address="not-a-hex")

        with patch("maafw_cli.core.reconnect.load_session", return_value=session), \
             patch("maafw_cli.maafw.init_toolkit"):
            with pytest.raises(DeviceConnectionError, match="Invalid saved hwnd"):
                from maafw_cli.core.reconnect import reconnect
                reconnect()
