"""
MaaFramework controller wrappers — unified re-exports.

Import public symbols from any sub-module via::

    from maafw_cli.maafw.controllers import connect_adb, find_adb_devices
"""
from maafw_cli.maafw.controllers.adb import AdbDeviceInfo, find_adb_devices, connect_adb
from maafw_cli.maafw.controllers.win32 import Win32WindowInfo, find_win32_windows, connect_win32
from maafw_cli.maafw.controllers.playcover import connect_playcover
from maafw_cli.maafw.controllers.wlroots import connect_wlroots
from maafw_cli.maafw.controllers.dbg import connect_dbg

__all__ = [
    "AdbDeviceInfo", "find_adb_devices", "connect_adb",
    "Win32WindowInfo", "find_win32_windows", "connect_win32",
    "connect_playcover",
    "connect_wlroots",
    "connect_dbg",
]
