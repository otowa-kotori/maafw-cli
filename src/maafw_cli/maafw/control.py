"""
Control operations — click, etc. via MaaFramework controller.
"""
from __future__ import annotations

import logging

from maa.controller import Controller

from maafw_cli.core.log import Timer

_log = logging.getLogger("maafw_cli.control")


def click(controller: Controller, x: int, y: int) -> bool:
    """Perform a single tap/click at (*x*, *y*).

    Uses ``post_click`` which works across both ADB and Win32 controllers.
    """
    with Timer("click", log=_log):
        return controller.post_click(x, y).wait().succeeded
