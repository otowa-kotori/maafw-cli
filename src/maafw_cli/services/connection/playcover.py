"""
PlayCover connection service.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.registry import service


def _connect_playcover_inner(
    address: str,
    uuid: str,
) -> tuple[dict[str, Any], Any]:
    """Connect to a PlayCover iOS application.

    Returns (result_dict, Controller) — no side effects.
    """
    init_toolkit()
    logger.info("Connecting to PlayCover at '%s' (uuid=%s)...", address, uuid)

    from maafw_cli.maafw.controllers.playcover import connect_playcover as _connect

    controller = _connect(address, uuid)
    if controller is None:
        raise DeviceConnectionError(
            f"Failed to connect to PlayCover at '{address}' (uuid={uuid})."
        )

    result = {
        "type": "playcover",
        "address": address,
        "uuid": uuid,
    }

    return result, controller


@service(
    name="connect_playcover",
    needs_session=False,
    human=lambda r: f"Connected to PlayCover at {r.get('address', '?')} as '{r.get('session', 'default')}'",
)
def do_connect_playcover(
    address: str,
    uuid: str,
    session_name: str = "default",
) -> dict:
    """Connect to a PlayCover iOS application (direct-call fallback for DISPATCH table)."""
    result, _controller = _connect_playcover_inner(address, uuid)
    result["session"] = session_name
    return result
