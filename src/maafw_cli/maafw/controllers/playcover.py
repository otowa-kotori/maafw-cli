"""
PlayCover controller connection — thin wrapper around MaaFramework.

PlayCoverController is used for macOS iOS applications via PlayCover.
There is no device-discovery API; the caller must supply address and UUID.
"""
from __future__ import annotations

import logging

from maa.controller import PlayCoverController

from maafw_cli.core.log import Timer

_log = logging.getLogger("maafw_cli.playcover")


def connect_playcover(
    address: str,
    uuid: str,
) -> PlayCoverController | None:
    """Create and connect a PlayCoverController.

    *address* is the PlayCover relay address and *uuid* identifies
    the application instance.

    Returns the connected controller, or ``None`` on failure.
    """
    ctrl = PlayCoverController(address, uuid)
    with Timer("PlayCover connection", log=_log):
        if not ctrl.post_connection().wait().succeeded:
            if hasattr(ctrl, "destroy"):
                ctrl.destroy()
            return None
    return ctrl
