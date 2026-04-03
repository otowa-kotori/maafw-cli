"""
Debug controller connection — thin wrapper around MaaFramework.

DbgController replays pre-recorded images or recordings for offline
testing / debugging.  There is no device-discovery API.
"""
from __future__ import annotations

import logging
from typing import Any

from maa.controller import DbgController
from maa.define import MaaDbgControllerTypeEnum

from maafw_cli.core.log import Timer

_log = logging.getLogger("maafw_cli.dbg")


def connect_dbg(
    read_path: str,
    write_path: str,
    dbg_type: int = MaaDbgControllerTypeEnum.CarouselImage,
    config: dict[str, Any] | None = None,
) -> DbgController | None:
    """Create and connect a DbgController.

    *read_path*  — directory containing images / recordings to replay.
    *write_path* — directory for writing debug output.
    *dbg_type*   — ``MaaDbgControllerTypeEnum.CarouselImage`` (1) or
                   ``MaaDbgControllerTypeEnum.ReplayRecording`` (2).
    *config*     — optional extra config dict.

    Returns the connected controller, or ``None`` on failure.
    """
    ctrl = DbgController(read_path, write_path, dbg_type, config or {})
    with Timer("Dbg connection", log=_log):
        if not ctrl.post_connection().wait().succeeded:
            if hasattr(ctrl, "destroy"):
                ctrl.destroy()
            return None
    return ctrl
