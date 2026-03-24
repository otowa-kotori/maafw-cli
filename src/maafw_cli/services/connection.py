"""
Connection services — device discovery, ADB / Win32 connect.

These services don't use ``ServiceContext.controller`` (they *create* it).
They interact with Toolkit and session persistence directly.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import ConnectionError
from maafw_cli.core.log import logger
from maafw_cli.core.session import SessionInfo, save_session
from maafw_cli.services.registry import service


def _init_toolkit() -> None:
    """Initialise MaaFramework toolkit (safe to call multiple times)."""
    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass


@service(name="device_list")
def do_device_list(*, adb: bool = True, win32: bool = False) -> dict:
    """List available devices / windows."""
    _init_toolkit()
    result: dict = {}

    if adb:
        from maafw_cli.maafw.adb import find_adb_devices
        devices = find_adb_devices()
        result["adb"] = [
            {"name": d.name, "address": d.address, "adb_path": d.adb_path}
            for d in devices
        ]

    if win32:
        from maafw_cli.maafw.win32 import find_win32_windows
        windows = find_win32_windows()
        result["win32"] = [
            {"hwnd": hex(w.hwnd), "window_name": w.window_name, "class_name": w.class_name}
            for w in windows
        ]

    return result


# ── inner connect functions (reusable by daemon) ──────────────


def _connect_adb_inner(
    device: str,
    screenshot_size: int = 720,
) -> tuple[dict[str, Any], Any, SessionInfo]:
    """Connect to an ADB device.

    Returns (result_dict, Controller, SessionInfo) — no side effects.
    """
    _init_toolkit()
    logger.info("Connecting to ADB device '%s'...", device)

    from maafw_cli.maafw.adb import find_adb_devices, connect_adb as _connect

    devices = find_adb_devices()
    match = None
    for d in devices:
        if d.name == device or d.address == device:
            match = d
            break

    if match is None:
        raise ConnectionError(
            f"Device '{device}' not found. Available: {[d.name for d in devices]}"
        )

    controller = _connect(match, screenshot_short_side=screenshot_size)
    if controller is None:
        raise ConnectionError(f"Failed to connect to '{device}'.")

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
    _init_toolkit()
    logger.info("Connecting to Win32 window '%s'...", window)

    from maafw_cli.maafw.win32 import find_win32_windows, connect_win32 as _connect

    windows = find_win32_windows()

    if window.startswith("0x") or window.startswith("0X"):
        try:
            target_hwnd = int(window, 16)
        except ValueError:
            raise ConnectionError(f"Invalid hwnd: '{window}'.")
        matches = [w for w in windows if w.hwnd == target_hwnd]
    else:
        needle = window.lower()
        matches = [w for w in windows if needle in w.window_name.lower()]

    if not matches:
        raise ConnectionError(
            f"No window matching '{window}'. Use 'device list --win32' to see available windows."
        )

    if len(matches) > 1:
        listing = "\n".join(f"  {hex(m.hwnd):<14s} {m.window_name}" for m in matches)
        raise ConnectionError(
            f"Multiple windows match '{window}'. Be more specific:\n{listing}"
        )

    matched = matches[0]

    from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum

    sc_val = int(getattr(MaaWin32ScreencapMethodEnum, screencap_method))
    in_val = int(getattr(MaaWin32InputMethodEnum, input_method))

    controller = _connect(matched, screencap_method=sc_val, input_method=in_val)
    if controller is None:
        raise ConnectionError(
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


@service(name="connect_adb")
def do_connect_adb(device: str, screenshot_size: int = 720) -> dict:
    """Connect to an ADB device and persist session."""
    result, _controller, info = _connect_adb_inner(device, screenshot_size)

    save_session(info)

    result["session"] = "default"
    return result


@service(name="connect_win32")
def do_connect_win32(
    window: str,
    screencap_method: str = "FramePool",
    input_method: str = "PostMessage",
) -> dict:
    """Connect to a Win32 window and persist session."""
    result, _controller, info = _connect_win32_inner(window, screencap_method, input_method)

    save_session(info)

    result["session"] = "default"
    return result
