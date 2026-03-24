"""
Shared reconnection helper for CLI commands.

Phase 1 uses file-based session: reads session.json, rediscovers the device,
and reconnects.  Phase 3 will replace this with daemon IPC.
"""
from __future__ import annotations

import logging

from maa.controller import Controller

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import Timer
from maafw_cli.core.session import load_session

_log = logging.getLogger("maafw_cli.reconnect")


def reconnect() -> Controller:
    """Re-establish a MaaFW connection from the saved session file.

    Raises :class:`DeviceConnectionError` if anything goes wrong.
    """
    with Timer("total reconnect", log=_log):
        session = load_session()
        if session is None:
            raise DeviceConnectionError(
                "No active session. Run 'maafw-cli connect adb <device>' first."
            )

        _log.debug("session loaded from file")

        # Initialise MaaFW toolkit (idempotent)
        with Timer("toolkit init", log=_log):
            from maafw_cli.maafw import init_toolkit
            init_toolkit()

        if session.type == "adb":
            return _reconnect_adb(session)
        elif session.type == "win32":
            return _reconnect_win32(session)

        raise DeviceConnectionError(f"Unsupported session type: {session.type}")


def _reconnect_adb(session) -> Controller:
    from maafw_cli.maafw.adb import find_adb_devices, connect_adb

    with Timer("device discovery", log=_log):
        devices = find_adb_devices()

    match = None
    for d in devices:
        if d.name == session.device or d.address == session.address:
            match = d
            break

    if match is None:
        raise DeviceConnectionError(
            f"Session device '{session.device}' no longer available."
        )

    with Timer("ADB connection", log=_log):
        controller = connect_adb(match, screenshot_short_side=session.screenshot_short_side)

    if controller is None:
        raise DeviceConnectionError(
            f"Failed to reconnect to '{session.device}'."
        )
    return controller


def _reconnect_win32(session) -> Controller:
    from maafw_cli.maafw.win32 import find_win32_windows, connect_win32

    with Timer("window discovery", log=_log):
        windows = find_win32_windows()

    # Match by window title (more stable than hwnd across restarts)
    needle = session.window_name.lower() if session.window_name else ""
    match = None
    for w in windows:
        if needle and needle in w.window_name.lower():
            match = w
            break

    if match is None:
        raise DeviceConnectionError(
            f"Session window '{session.window_name}' no longer available."
        )

    with Timer("Win32 connection", log=_log):
        controller = connect_win32(
            match,
            screencap_method=session.screencap_methods,
            input_method=session.input_methods,
        )

    if controller is None:
        raise DeviceConnectionError(
            f"Failed to reconnect to '{session.window_name}'."
        )
    return controller
