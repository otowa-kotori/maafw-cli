"""
Shared reconnection helper for CLI commands.

Phase 1 uses file-based session: reads session.json, rediscovers the device,
and reconnects.  Phase 3 will replace this with daemon IPC.
"""
from __future__ import annotations

import logging

from maa.controller import Controller

from maafw_cli.core.log import Timer
from maafw_cli.core.output import OutputFormatter
from maafw_cli.core.session import load_session

_log = logging.getLogger("maafw_cli.reconnect")

_EXIT_CONNECTION_ERROR = 3


def reconnect(fmt: OutputFormatter) -> Controller:
    """Re-establish a MaaFW connection from the saved session file.

    Calls ``fmt.error(…)`` (which exits) if anything goes wrong,
    so callers can assume the return value is always a live Controller.
    """
    with Timer("total reconnect", log=_log):
        session = load_session()
        if session is None:
            fmt.error(
                "No active session. Run 'maafw-cli connect adb <device>' first.",
                exit_code=_EXIT_CONNECTION_ERROR,
            )

        _log.debug("session loaded from file")

        # Initialise MaaFW toolkit (idempotent)
        with Timer("toolkit init", log=_log):
            _init_toolkit()

        if session.type == "adb":
            return _reconnect_adb(fmt, session)

        fmt.error(f"Unsupported session type: {session.type}", exit_code=_EXIT_CONNECTION_ERROR)


def _init_toolkit() -> None:
    """Initialise MaaFramework toolkit (safe to call multiple times)."""
    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass


def _reconnect_adb(fmt: OutputFormatter, session) -> Controller:
    from maafw_cli.maafw.adb import find_adb_devices, connect_adb

    with Timer("device discovery", log=_log):
        devices = find_adb_devices()

    match = None
    for d in devices:
        if d.name == session.device or d.address == session.address:
            match = d
            break

    if match is None:
        fmt.error(
            f"Session device '{session.device}' no longer available.",
            exit_code=_EXIT_CONNECTION_ERROR,
        )

    with Timer("ADB connection", log=_log):
        controller = connect_adb(match, screenshot_short_side=session.screenshot_short_side)

    if controller is None:
        fmt.error(
            f"Failed to reconnect to '{session.device}'.",
            exit_code=_EXIT_CONNECTION_ERROR,
        )
    return controller
