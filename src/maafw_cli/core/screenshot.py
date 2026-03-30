"""
Screenshot size configuration — shared by ADB and Win32 controllers.

Parses CLI ``--size`` values (``short:720``, ``long:1920``, ``raw``) and
applies the corresponding MaaFramework controller method.
"""
from __future__ import annotations

from typing import Any


def parse_size_option(size: str) -> tuple[str, int | None]:
    """Parse a ``--size`` string into ``(mode, value)``.

    Returns:
        ``("short", 720)``, ``("long", 1920)``, or ``("raw", None)``.

    Raises:
        ValueError: If the format is unrecognised.
    """
    s = size.strip().lower()
    if s == "raw":
        return ("raw", None)
    if ":" in s:
        prefix, _, rest = s.partition(":")
        if prefix in ("short", "long"):
            try:
                value = int(rest)
            except ValueError:
                raise ValueError(
                    f"Invalid size value '{rest}' — expected an integer after '{prefix}:'."
                )
            if value <= 0:
                raise ValueError(
                    f"Size value must be positive, got {value}."
                )
            return (prefix, value)
    raise ValueError(
        f"Invalid --size format '{size}'. "
        "Expected 'short:<pixels>', 'long:<pixels>', or 'raw'."
    )


def apply_size_option(ctrl: Any, size: str) -> None:
    """Parse *size* and call the matching controller method.

    *ctrl* must expose ``set_screenshot_target_short_side``,
    ``set_screenshot_target_long_side``, and ``set_screenshot_use_raw_size``.
    """
    mode, value = parse_size_option(size)
    if mode == "short":
        ctrl.set_screenshot_target_short_side(value)
    elif mode == "long":
        ctrl.set_screenshot_target_long_side(value)
    else:
        ctrl.set_screenshot_use_raw_size(True)
