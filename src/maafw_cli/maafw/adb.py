"""
Backward-compatible re-export — actual implementation lives in
``maafw_cli.maafw.controllers.adb``.
"""
from maafw_cli.maafw.controllers.adb import *  # noqa: F401,F403
from maafw_cli.maafw.controllers.adb import AdbDeviceInfo, find_adb_devices, connect_adb  # noqa: F811

__all__ = ["AdbDeviceInfo", "find_adb_devices", "connect_adb"]
