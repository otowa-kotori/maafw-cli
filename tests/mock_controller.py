"""
MockController for service-level testing.

Simulates MaaFW Controller without any real device or MaaFW dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
        connected: bool = True,
    ):
        self.click_ok = click_ok
        self.swipe_ok = swipe_ok
        self.scroll_ok = scroll_ok
        self.key_ok = key_ok
        self.type_ok = type_ok
        self.connected = connected

        # Call records
        self.clicks: list[tuple] = []
        self.swipes: list[tuple] = []
        self.scrolls: list[tuple] = []
        self.keys: list[int] = []
        self.texts: list[str] = []

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
