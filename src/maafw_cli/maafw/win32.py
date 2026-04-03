"""
Backward-compatible re-export — actual implementation lives in
``maafw_cli.maafw.controllers.win32``.
"""
from maafw_cli.maafw.controllers.win32 import *  # noqa: F401,F403
from maafw_cli.maafw.controllers.win32 import Win32WindowInfo, find_win32_windows, connect_win32  # noqa: F811

__all__ = ["Win32WindowInfo", "find_win32_windows", "connect_win32"]
