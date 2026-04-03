"""
Device discovery service.
"""
from __future__ import annotations

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
