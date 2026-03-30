"""
Connection services — device discovery, ADB / Win32 connect.

These services don't use ``ServiceContext.controller`` (they *create* it).
They interact with Toolkit directly.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.registry import service


@service(name="device_list", needs_session=False)
def do_device_list(*, adb: bool = True, win32: bool = False, filter: str | None = None) -> dict:
    """List available devices / windows.

    When *filter* is provided, only entries whose name/address/window_name
    or class_name contain the substring (case-insensitive) are returned.
    """
    init_toolkit()
    result: dict = {}
    q = filter.lower() if filter else None

    if adb:
        from maafw_cli.maafw.adb import find_adb_devices
        devices = find_adb_devices()
        items = [
            {"name": d.name, "address": d.address, "adb_path": d.adb_path}
            for d in devices
        ]
        if q:
            items = [d for d in items if q in d["name"].lower() or q in d["address"].lower()]
        result["adb"] = items

    if win32:
        from maafw_cli.maafw.win32 import find_win32_windows
        windows = find_win32_windows()
        items = [
            {"hwnd": hex(w.hwnd), "window_name": w.window_name, "class_name": w.class_name}
            for w in windows
        ]
        if q:
            items = [w for w in items if q in w["window_name"].lower() or q in w["class_name"].lower()]
        result["win32"] = items

    return result


# ── inner connect functions (reusable by daemon) ──────────────


def _connect_adb_inner(
    device: str,
    screenshot_size: int = 720,
    screencap_method: str | None = None,
    input_method: str | None = None,
) -> tuple[dict[str, Any], Any]:
    """Connect to an ADB device.

    Returns (result_dict, Controller) — no side effects.
    """
    init_toolkit()
    logger.info("Connecting to ADB device '%s'...", device)

    from maafw_cli.maafw.adb import find_adb_devices, connect_adb as _connect

    devices = find_adb_devices()
    match = None
    for d in devices:
        if d.name == device or d.address == device:
            match = d
            break

    if match is None:
        raise DeviceConnectionError(
            f"Device '{device}' not found. Available: {[d.name for d in devices]}"
        )

    from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum

    sc_val = None
    if screencap_method is not None:
        sc_val = _parse_method_flags(screencap_method, MaaAdbScreencapMethodEnum, "screencap_method")
    in_val = None
    if input_method is not None:
        in_val = _parse_method_flags(input_method, MaaAdbInputMethodEnum, "input_method")

    controller = _connect(
        match,
        screenshot_short_side=screenshot_size,
        screencap_methods=sc_val,
        input_methods=in_val,
    )
    if controller is None:
        raise DeviceConnectionError(f"Failed to connect to '{device}'.")

    result = {
        "type": "adb",
        "device": match.name,
        "address": match.address,
    }

    return result, controller


def _parse_method_flags(value: str, enum_cls: type, param_name: str) -> int:
    """Parse a method string like ``"FramePool,PrintWindow"`` into OR'd enum flags.

    Accepts:
    - Single name: ``"FramePool"``
    - Combined names: ``"FramePool,PrintWindow"``
    - Integer: ``"18"``
    """
    # Try as integer first
    try:
        return int(value, 0)
    except ValueError:
        pass

    valid = [a for a in dir(enum_cls) if not a.startswith("_")]
    parts = [p.strip() for p in value.split(",")]
    result = 0
    for part in parts:
        try:
            result |= int(getattr(enum_cls, part))
        except AttributeError:
            raise DeviceConnectionError(
                f"Invalid {param_name} '{part}'. Valid: {', '.join(valid)}"
            )
    return result


def _connect_win32_inner(
    window: str,
    screencap_method: str = "FramePool,PrintWindow",
    input_method: str = "PostMessage",
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

    controller = _connect(matched, screencap_method=sc_val, input_method=in_val)
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


# ── public service wrappers (daemon handles session creation) ──


@service(
    name="connect_adb",
    needs_session=False,
    human=lambda r: f"Connected to {r.get('device', '?')} ({r.get('address', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_adb(
    device: str,
    screenshot_size: int = 720,
    screencap_method: str | None = None,
    input_method: str | None = None,
    session_name: str = "default",
) -> dict:
    """Connect to an ADB device (direct-call fallback for DISPATCH table).

    In daemon mode, the server handles session creation directly via
    ``_connect_adb_inner``.  This wrapper exists only so the service is
    registered in DISPATCH for action-name lookup.
    """
    result, _controller = _connect_adb_inner(
        device, screenshot_size, screencap_method, input_method,
    )
    result["session"] = session_name
    return result


@service(
    name="connect_win32",
    needs_session=False,
    human=lambda r: f"Connected to {r.get('window_name', '?')} ({r.get('hwnd', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_win32(
    window: str,
    screencap_method: str = "FramePool,PrintWindow",
    input_method: str = "PostMessage",
    session_name: str = "default",
) -> dict:
    """Connect to a Win32 window (direct-call fallback for DISPATCH table).

    In daemon mode, the server handles session creation directly via
    ``_connect_win32_inner``.
    """
    result, _controller = _connect_win32_inner(window, screencap_method, input_method)
    result["session"] = session_name
    return result
