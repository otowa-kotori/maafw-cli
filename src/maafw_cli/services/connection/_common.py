"""
Shared helpers for connection services.
"""
from __future__ import annotations

from maafw_cli.core.errors import DeviceConnectionError


def _parse_method_flags(value: str, enum_cls: type, param_name: str) -> int:
    """Parse a method string like ``"FramePool,PrintWindow"`` into OR'd enum flags.

    Accepts:
    - Single name: ``"FramePool"``
    - Combined names: ``"FramePool,PrintWindow"``
    - Integer: ``"18"``
    """
    # Try as integer first
    try:
        return int(value, 0)
    except ValueError:
        pass

    valid = [a for a in dir(enum_cls) if not a.startswith("_")]
    parts = [p.strip() for p in value.split(",")]
    result = 0
    for part in parts:
        try:
            result |= int(getattr(enum_cls, part))
        except AttributeError:
            raise DeviceConnectionError(
                f"Invalid {param_name} '{part}'. Valid: {', '.join(valid)}"
            )
    return result
