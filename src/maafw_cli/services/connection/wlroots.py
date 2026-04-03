"""
WlRoots connection service.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.registry import service


def _connect_wlroots_inner(
    wlr_socket_path: str,
) -> tuple[dict[str, Any], Any]:
    """Connect to a wlroots Wayland compositor.

    Returns (result_dict, Controller) — no side effects.
    """
    init_toolkit()
    logger.info("Connecting to WlRoots at '%s'...", wlr_socket_path)

    from maafw_cli.maafw.controllers.wlroots import connect_wlroots as _connect

    controller = _connect(wlr_socket_path)
    if controller is None:
        raise DeviceConnectionError(
            f"Failed to connect to WlRoots at '{wlr_socket_path}'."
        )

    result = {
        "type": "wlroots",
        "wlr_socket_path": wlr_socket_path,
    }

    return result, controller


@service(
    name="connect_wlroots",
    needs_session=False,
    human=lambda r: f"Connected to WlRoots at {r.get('wlr_socket_path', '?')} as '{r.get('session', 'default')}'",
)
def do_connect_wlroots(
    wlr_socket_path: str,
    session_name: str = "default",
) -> dict:
    """Connect to a wlroots compositor (direct-call fallback for DISPATCH table)."""
    result, _controller = _connect_wlroots_inner(wlr_socket_path)
    result["session"] = session_name
    return result
