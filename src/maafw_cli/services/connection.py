"""
Connection services — device discovery, ADB / Win32 connect.

These services don't use ``ServiceContext.controller`` (they *create* it).
They interact with Toolkit and session persistence directly.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.core.session import SessionInfo, save_session
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
) -> tuple[dict[str, Any], Any, SessionInfo]:
    """Connect to an ADB device.

    Returns (result_dict, Controller, SessionInfo) — no side effects.
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

    controller = _connect(match, screenshot_short_side=screenshot_size)
    if controller is None:
        raise DeviceConnectionError(f"Failed to connect to '{device}'.")

    info = SessionInfo(
        type="adb",
        device=match.name,
        adb_path=match.adb_path,
        address=match.address,
        screencap_methods=match.screencap_methods,
        input_methods=match.input_methods,
        config=match.config,
        screenshot_short_side=screenshot_size,
    )

    result = {
        "type": "adb",
        "device": match.name,
        "address": match.address,
    }

    return result, controller, info


def _connect_win32_inner(
    window: str,
    screencap_method: str = "FramePool",
    input_method: str = "PostMessage",
) -> tuple[dict[str, Any], Any, SessionInfo]:
    """Connect to a Win32 window.

    Returns (result_dict, Controller, SessionInfo) — no side effects.
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

    try:
        sc_val = int(getattr(MaaWin32ScreencapMethodEnum, screencap_method))
    except AttributeError:
        valid = [a for a in dir(MaaWin32ScreencapMethodEnum) if not a.startswith("_")]
        raise DeviceConnectionError(
            f"Invalid screencap_method '{screencap_method}'. Valid: {', '.join(valid)}"
        )
    try:
        in_val = int(getattr(MaaWin32InputMethodEnum, input_method))
    except AttributeError:
        valid = [a for a in dir(MaaWin32InputMethodEnum) if not a.startswith("_")]
        raise DeviceConnectionError(
            f"Invalid input_method '{input_method}'. Valid: {', '.join(valid)}"
        )

    controller = _connect(matched, screencap_method=sc_val, input_method=in_val)
    if controller is None:
        raise DeviceConnectionError(
            f"Failed to connect to '{matched.window_name}' ({hex(matched.hwnd)})."
        )

    info = SessionInfo(
        type="win32",
        device=matched.window_name,
        address=hex(matched.hwnd),
        screencap_methods=sc_val,
        input_methods=in_val,
        window_name=matched.window_name,
    )

    result = {
        "type": "win32",
        "window_name": matched.window_name,
        "hwnd": hex(matched.hwnd),
        "class_name": matched.class_name,
    }

    return result, controller, info


# ── public service wrappers (thin: call inner + persist) ──────


@service(
    name="connect_adb",
    needs_session=False,
    human=lambda r: f"Connected to {r.get('device', '?')} ({r.get('address', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_adb(device: str, screenshot_size: int = 720, session_name: str = "default") -> dict:
    """Connect to an ADB device and persist session."""
    result, _controller, info = _connect_adb_inner(device, screenshot_size)

    info.name = session_name
    save_session(info)

    result["session"] = session_name
    return result


@service(
    name="connect_win32",
    needs_session=False,
    human=lambda r: f"Connected to {r.get('window_name', '?')} ({r.get('hwnd', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_win32(
    window: str,
    screencap_method: str = "FramePool",
    input_method: str = "PostMessage",
    session_name: str = "default",
) -> dict:
    """Connect to a Win32 window and persist session."""
    result, _controller, info = _connect_win32_inner(window, screencap_method, input_method)

    info.name = session_name
    save_session(info)

    result["session"] = session_name
    return result
