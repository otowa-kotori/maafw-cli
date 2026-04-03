"""
Win32 connection service.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.connection._common import _parse_method_flags
from maafw_cli.services.registry import service


def _connect_win32_inner(
    window: str,
    screencap_method: str = "FramePool,PrintWindow",
    input_method: str = "PostMessage",
    size: str = "raw",
) -> tuple[dict[str, Any], Any]:
    """Connect to a Win32 window.

    Returns (result_dict, Controller) — no side effects.
    """
    init_toolkit()
    logger.info("Connecting to Win32 window '%s'...", window)

    from maafw_cli.maafw.win32 import find_win32_windows, connect_win32 as _connect

    windows = find_win32_windows()

    if window.startswith("0x") or window.startswith("0X"):
        try:
            target_hwnd = int(window, 16)
        except ValueError:
            raise DeviceConnectionError(f"Invalid hwnd: '{window}'.")
        matches = [w for w in windows if w.hwnd == target_hwnd]
    else:
        needle = window.lower()
        matches = [w for w in windows if needle in w.window_name.lower()]

    if not matches:
        raise DeviceConnectionError(
            f"No window matching '{window}'. Use 'device win32' to see available windows."
        )

    if len(matches) > 1:
        listing = "\n".join(f"  {hex(m.hwnd):<14s} {m.window_name}" for m in matches)
        raise DeviceConnectionError(
            f"Multiple windows match '{window}'. Be more specific:\n{listing}"
        )

    matched = matches[0]

    from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum

    sc_val = _parse_method_flags(screencap_method, MaaWin32ScreencapMethodEnum, "screencap_method")
    in_val = _parse_method_flags(input_method, MaaWin32InputMethodEnum, "input_method")

    controller = _connect(matched, screencap_method=sc_val, input_method=in_val, size=size)
    if controller is None:
        raise DeviceConnectionError(
            f"Failed to connect to '{matched.window_name}' ({hex(matched.hwnd)})."
        )

    result = {
        "type": "win32",
        "window_name": matched.window_name,
        "hwnd": hex(matched.hwnd),
        "class_name": matched.class_name,
    }

    return result, controller


@service(
    name="connect_win32",
    needs_session=False,
    human=lambda r: f"Connected to {r.get('window_name', '?')} ({r.get('hwnd', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_win32(
    window: str,
    screencap_method: str = "FramePool,PrintWindow",
    input_method: str = "PostMessage",
    size: str = "raw",
    session_name: str = "default",
) -> dict:
    """Connect to a Win32 window (direct-call fallback for DISPATCH table).

    In daemon mode, the server handles session creation directly via
    ``_connect_win32_inner``.
    """
    result, _controller = _connect_win32_inner(window, screencap_method, input_method, size=size)
    result["session"] = session_name
    return result
