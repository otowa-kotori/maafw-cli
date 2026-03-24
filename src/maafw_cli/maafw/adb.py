"""
ADB device discovery and connection — thin wrapper around MaaFramework.

This module is independent of the CLI layer and can be used by any caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from maa.toolkit import Toolkit
from maa.controller import AdbController


@dataclass
class AdbDeviceInfo:
    """Human-readable summary of a discovered ADB device."""
    name: str
    adb_path: str
    address: str
    screencap_methods: int
    input_methods: int
    config: dict[str, Any] = field(default_factory=dict)


def find_adb_devices() -> list[AdbDeviceInfo]:
    """Scan for connected ADB devices.  Returns a list of device info."""
    device_list = Toolkit.find_adb_devices()
    return [
        AdbDeviceInfo(
            name=str(d.name),
            adb_path=str(d.adb_path),
            address=str(d.address),
            screencap_methods=int(d.screencap_methods),
            input_methods=int(d.input_methods),
            config=dict(d.config) if isinstance(d.config, dict) else {},
        )
        for d in device_list
    ]


def connect_adb(device: AdbDeviceInfo, screenshot_short_side: int = 720) -> Optional[AdbController]:
    """Create and connect an AdbController for *device*.

    Returns the connected controller, or ``None`` on failure.
    """
    ctrl = AdbController(
        device.adb_path,
        device.address,
        device.screencap_methods,
        device.input_methods,
        device.config,
    )
    ctrl.set_screenshot_target_short_side(screenshot_short_side)
    if not ctrl.post_connection().wait().succeeded:
        return None
    return ctrl
