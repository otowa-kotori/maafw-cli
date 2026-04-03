"""
ADB connection service.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.connection._common import _parse_method_flags
from maafw_cli.services.registry import service


def _connect_adb_inner(
    device: str,
    size: str = "short:720",
    screencap_method: str | None = None,
    input_method: str | None = None,
) -> tuple[dict[str, Any], Any]:
    """Connect to an ADB device.

    Returns (result_dict, Controller) — no side effects.
    """
    init_toolkit()
    logger.info("Connecting to ADB device '%s'...", device)

    from maafw_cli.maafw.adb import find_adb_devices, connect_adb as _connect

    devices = find_adb_devices()
    match = None
    for d in devices:
        if d.name == device or d.address == device:
            match = d
            break

    if match is None:
        raise DeviceConnectionError(
            f"Device '{device}' not found. Available: {[d.name for d in devices]}"
        )

    from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum

    sc_val = None
    if screencap_method is not None:
        sc_val = _parse_method_flags(screencap_method, MaaAdbScreencapMethodEnum, "screencap_method")
    in_val = None
    if input_method is not None:
        in_val = _parse_method_flags(input_method, MaaAdbInputMethodEnum, "input_method")

    controller = _connect(
        match,
        size=size,
        screencap_methods=sc_val,
        input_methods=in_val,
    )
    if controller is None:
        raise DeviceConnectionError(f"Failed to connect to '{device}'.")

    result = {
        "type": "adb",
        "device": match.name,
        "address": match.address,
    }

    return result, controller


@service(
    name="connect_adb",
    needs_session=False,
    human=lambda r: f"Connected to {r.get('device', '?')} ({r.get('address', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_adb(
    device: str,
    size: str = "short:720",
    screencap_method: str | None = None,
    input_method: str | None = None,
    session_name: str = "default",
) -> dict:
    """Connect to an ADB device (direct-call fallback for DISPATCH table).

    In daemon mode, the server handles session creation directly via
    ``_connect_adb_inner``.  This wrapper exists only so the service is
    registered in DISPATCH for action-name lookup.
    """
    result, _controller = _connect_adb_inner(
        device, size, screencap_method, input_method,
    )
    result["session"] = session_name
    return result
