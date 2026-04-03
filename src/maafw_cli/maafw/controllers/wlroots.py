"""
WlRoots controller connection — thin wrapper around MaaFramework.

WlRootsController is used for Linux wlroots-based compositors.
There is no device-discovery API; the caller must supply the socket path.
"""
from __future__ import annotations

import logging

from maa.controller import WlRootsController

from maafw_cli.core.log import Timer

_log = logging.getLogger("maafw_cli.wlroots")


def connect_wlroots(
    wlr_socket_path: str,
) -> WlRootsController | None:
    """Create and connect a WlRootsController.

    *wlr_socket_path* is the path to the wlroots Wayland socket.

    Returns the connected controller, or ``None`` on failure.
    """
    ctrl = WlRootsController(wlr_socket_path)
    with Timer("WlRoots connection", log=_log):
        if not ctrl.post_connection().wait().succeeded:
            if hasattr(ctrl, "destroy"):
                ctrl.destroy()
            return None
    return ctrl
