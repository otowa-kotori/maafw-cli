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


def long_press(
    controller: Controller, x: int, y: int, duration: int = 1000
) -> bool:
    """Long-press at (*x*, *y*) for *duration* ms.

    Implemented as touch_down → sleep → touch_up.
    """
    import time

    with Timer("long_press", log=_log):
        job = controller.post_touch_down(x, y)
        if not job.wait().succeeded:
            return False
        time.sleep(duration / 1000.0)
        return controller.post_touch_up().wait().succeeded


def touch_down(
    controller: Controller, x: int, y: int, contact: int = 0, pressure: int = 1
) -> bool:
    """Touch down at (*x*, *y*)."""
    with Timer("touch_down", log=_log):
        return controller.post_touch_down(x, y, contact, pressure).wait().succeeded


def touch_move(
    controller: Controller, x: int, y: int, contact: int = 0, pressure: int = 1
) -> bool:
    """Move touch point to (*x*, *y*)."""
    with Timer("touch_move", log=_log):
        return controller.post_touch_move(x, y, contact, pressure).wait().succeeded


def touch_up(controller: Controller, contact: int = 0) -> bool:
    """Lift touch point."""
    with Timer("touch_up", log=_log):
        return controller.post_touch_up(contact).wait().succeeded


def key_down(controller: Controller, key: int) -> bool:
    """Press key down (without releasing)."""
    with Timer("key_down", log=_log):
        return controller.post_key_down(key).wait().succeeded


def key_up(controller: Controller, key: int) -> bool:
    """Release a previously pressed key."""
    with Timer("key_up", log=_log):
        return controller.post_key_up(key).wait().succeeded


def start_app(controller: Controller, intent: str) -> bool:
    """Start an app via ADB intent."""
    with Timer("start_app", log=_log):
        return controller.post_start_app(intent).wait().succeeded


def stop_app(controller: Controller, intent: str) -> bool:
    """Stop an app via ADB intent."""
    with Timer("stop_app", log=_log):
        return controller.post_stop_app(intent).wait().succeeded


def run_shell(controller: Controller, cmd: str, timeout: int = 20000) -> str:
    """Execute a shell command on the device and return stdout."""
    with Timer("shell", log=_log):
        job = controller.post_shell(cmd, timeout)
        job.wait()
        if not job.succeeded:
            return ""
        return job.get() or ""


def relative_move(controller: Controller, dx: int, dy: int) -> bool:
    """Move mouse cursor relatively by (*dx*, *dy*).  Win32 only."""
    with Timer("relative_move", log=_log):
        return controller.post_relative_move(dx, dy).wait().succeeded
