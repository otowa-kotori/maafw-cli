"""
Win32 window discovery and connection — thin wrapper around MaaFramework.

This module is independent of the CLI layer and can be used by any caller.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from maa.toolkit import Toolkit
from maa.controller import Win32Controller
from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum

from maafw_cli.core.log import Timer

_log = logging.getLogger("maafw_cli.win32")


@dataclass
class Win32WindowInfo:
    """Human-readable summary of a discovered Win32 window."""

    hwnd: int  # window handle (integer)
    class_name: str  # window class name
    window_name: str  # window title


def find_win32_windows() -> list[Win32WindowInfo]:
    """Discover visible Win32 windows with non-empty titles."""
    with Timer("window discovery", log=_log):
        windows = Toolkit.find_desktop_windows()
    return [
        Win32WindowInfo(
            hwnd=int(w.hwnd) if w.hwnd is not None else 0,
            class_name=str(w.class_name),
            window_name=str(w.window_name),
        )
        for w in windows
        if w.window_name and w.window_name.strip()
    ]


def connect_win32(
    window: Win32WindowInfo,
    screencap_method: int = MaaWin32ScreencapMethodEnum.FramePool,
    input_method: int = MaaWin32InputMethodEnum.PostMessage,
) -> Win32Controller | None:
    """Create and connect a Win32Controller for *window*.

    Returns the connected controller, or ``None`` on failure.
    """
    ctrl = Win32Controller(
        window.hwnd,
        screencap_method,
        input_method,      # key input
        input_method,      # touch input (same as key for simplicity)
    )
    with Timer("Win32 connection", log=_log):
        if not ctrl.post_connection().wait().succeeded:
            if hasattr(ctrl, "destroy"):
                ctrl.destroy()
            return None
    return ctrl
