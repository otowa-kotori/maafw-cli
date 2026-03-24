"""
Control operations — click, swipe, scroll, key, text via MaaFramework controller.
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


def swipe(
    controller: Controller, x1: int, y1: int, x2: int, y2: int, duration: int = 300
) -> bool:
    """Swipe from (*x1*, *y1*) to (*x2*, *y2*) over *duration* ms."""
    with Timer("swipe", log=_log):
        return controller.post_swipe(x1, y1, x2, y2, duration).wait().succeeded


def scroll(controller: Controller, dx: int, dy: int) -> bool:
    """Scroll by (*dx*, *dy*).  Use multiples of 120 (WHEEL_DELTA)."""
    with Timer("scroll", log=_log):
        return controller.post_scroll(dx, dy).wait().succeeded


def input_text(controller: Controller, text: str) -> bool:
    """Type *text* into the focused control."""
    with Timer("input_text", log=_log):
        return controller.post_input_text(text).wait().succeeded


def press_key(controller: Controller, key: int) -> bool:
    """Press a single virtual key code."""
    with Timer("press_key", log=_log):
        return controller.post_click_key(key).wait().succeeded
