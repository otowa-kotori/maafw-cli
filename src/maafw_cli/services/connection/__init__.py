"""
Connection services — device discovery and controller connect.

All public symbols are re-exported here so existing imports like
``from maafw_cli.services.connection import do_connect_adb`` keep working.
"""
# Device discovery
from maafw_cli.services.connection.device import do_device_list

# Inner connect functions (used by daemon / local executor)
from maafw_cli.services.connection.adb import _connect_adb_inner, do_connect_adb
from maafw_cli.services.connection.win32 import _connect_win32_inner, do_connect_win32
from maafw_cli.services.connection.playcover import _connect_playcover_inner, do_connect_playcover
from maafw_cli.services.connection.wlroots import _connect_wlroots_inner, do_connect_wlroots

# Shared helpers
from maafw_cli.services.connection._common import _parse_method_flags

__all__ = [
    "do_device_list",
    "_connect_adb_inner", "do_connect_adb",
    "_connect_win32_inner", "do_connect_win32",
    "_connect_playcover_inner", "do_connect_playcover",
    "_connect_wlroots_inner", "do_connect_wlroots",
    "_parse_method_flags",
]
