"""
Control operations — click, etc. via MaaFramework controller.
"""
from __future__ import annotations

import logging
import time

from maa.controller import Controller

from maafw_cli.core.log import Timer

_log = logging.getLogger("maafw_cli.control")


def click(controller: Controller, x: int, y: int, *, duration: int = 50) -> bool:
    """Perform a single tap/click at (*x*, *y*).

    *duration* is press time in milliseconds.
    """
    with Timer("click", log=_log):
        if not controller.post_touch_down(x, y, contact=0).wait().succeeded:
            return False
        time.sleep(duration / 1000.0)
        return controller.post_touch_up(contact=0).wait().succeeded
