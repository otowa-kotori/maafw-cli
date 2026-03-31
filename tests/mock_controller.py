"""
MockController for service-level testing.

Simulates MaaFW Controller without any real device or MaaFW dependency.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MockJob:
    """Fake Job that can be .wait().succeeded."""

    _succeeded: bool = True

    def wait(self):
        return self

    @property
    def succeeded(self):
        return self._succeeded

    def get(self):
        """For screencap jobs that return an image."""
        return None


@dataclass
class MockJobWithResult:
    """Fake JobWithResult — .wait().succeeded + .get() returns a string."""

    _succeeded: bool = True
    _result: str = ""

    def wait(self):
        return self

    @property
    def succeeded(self):
        return self._succeeded

    def get(self):
        return self._result


class MockController:
    """Fake MaaFW Controller for service-level tests.

    Records every call so tests can assert what was dispatched.
    """

    def __init__(
        self,
        *,
        click_ok: bool = True,
        swipe_ok: bool = True,
        scroll_ok: bool = True,
        key_ok: bool = True,
        type_ok: bool = True,
        touch_ok: bool = True,
        startapp_ok: bool = True,
        stopapp_ok: bool = True,
        shell_ok: bool = True,
        shell_output: str = "",
        mousemove_ok: bool = True,
        connected: bool = True,
    ):
        self.click_ok = click_ok
        self.swipe_ok = swipe_ok
        self.scroll_ok = scroll_ok
        self.key_ok = key_ok
        self.type_ok = type_ok
        self.touch_ok = touch_ok
        self.startapp_ok = startapp_ok
        self.stopapp_ok = stopapp_ok
        self.shell_ok = shell_ok
        self.shell_output = shell_output
        self.mousemove_ok = mousemove_ok
        self.connected = connected

        # Call records
        self.clicks: list[tuple] = []
        self.swipes: list[tuple] = []
        self.scrolls: list[tuple] = []
        self.keys: list[int] = []
        self.texts: list[str] = []
        self.touch_downs: list[tuple] = []
        self.touch_moves: list[tuple] = []
        self.touch_ups: list[int] = []
        self.key_downs: list[int] = []
        self.key_ups: list[int] = []
        self.start_apps: list[str] = []
        self.stop_apps: list[str] = []
        self.shells: list[tuple] = []
        self.relative_moves: list[tuple] = []

    def post_click(self, x, y, contact=0, pressure=1):
        self.clicks.append((x, y))
        return MockJob(self.click_ok)

    def post_swipe(self, x1, y1, x2, y2, duration, contact=0, pressure=1):
        self.swipes.append((x1, y1, x2, y2, duration))
        return MockJob(self.swipe_ok)

    def post_scroll(self, dx, dy):
        self.scrolls.append((dx, dy))
        return MockJob(self.scroll_ok)

    def post_click_key(self, key):
        self.keys.append(key)
        return MockJob(self.key_ok)

    def post_input_text(self, text):
        self.texts.append(text)
        return MockJob(self.type_ok)

    def post_touch_down(self, x, y, contact=0, pressure=1):
        self.touch_downs.append((x, y, contact, pressure))
        return MockJob(self.touch_ok)

    def post_touch_move(self, x, y, contact=0, pressure=1):
        self.touch_moves.append((x, y, contact, pressure))
        return MockJob(self.touch_ok)

    def post_touch_up(self, contact=0):
        self.touch_ups.append(contact)
        return MockJob(self.touch_ok)

    def post_key_down(self, key):
        self.key_downs.append(key)
        return MockJob(self.key_ok)

    def post_key_up(self, key):
        self.key_ups.append(key)
        return MockJob(self.key_ok)

    def post_start_app(self, intent):
        self.start_apps.append(intent)
        return MockJob(self.startapp_ok)

    def post_stop_app(self, intent):
        self.stop_apps.append(intent)
        return MockJob(self.stopapp_ok)

    def post_shell(self, cmd, timeout=20000):
        self.shells.append((cmd, timeout))
        return MockJobWithResult(self.shell_ok, self.shell_output)

    def post_relative_move(self, dx, dy):
        self.relative_moves.append((dx, dy))
        return MockJob(self.mousemove_ok)
