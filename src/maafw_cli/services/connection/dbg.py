"""
Debug controller connection service.
"""
from __future__ import annotations

from typing import Any

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import logger
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.registry import service


_DBG_TYPE_NAMES: dict[str, int] = {
    "carousel_image": 1,
    "carouselimage": 1,
    "replay_recording": 2,
    "replayrecording": 2,
}


def _parse_dbg_type(value: str) -> int:
    """Parse a dbg_type string into an integer.

    Accepts:
    - Name: ``"carousel_image"``, ``"CarouselImage"``, ``"replay_recording"``, etc.
    - Integer: ``"1"`` or ``"2"``
    """
    try:
        return int(value, 0)
    except ValueError:
        pass

    lowered = value.lower().replace("-", "_")
    if lowered in _DBG_TYPE_NAMES:
        return _DBG_TYPE_NAMES[lowered]

    raise DeviceConnectionError(
        f"Invalid dbg_type '{value}'. "
        f"Valid: carousel_image (1), replay_recording (2)"
    )


def _connect_dbg_inner(
    read_path: str,
    write_path: str,
    dbg_type: str = "carousel_image",
    config: str | None = None,
) -> tuple[dict[str, Any], Any]:
    """Connect a debug controller.

    Returns (result_dict, Controller) — no side effects.
    """
    init_toolkit()
    dbg_type_int = _parse_dbg_type(dbg_type)
    logger.info(
        "Connecting DbgController (read=%s, write=%s, type=%d)...",
        read_path, write_path, dbg_type_int,
    )

    import json as _json
    config_dict: dict[str, Any] = {}
    if config:
        try:
            config_dict = _json.loads(config)
        except _json.JSONDecodeError as exc:
            raise DeviceConnectionError(f"Invalid --config JSON: {exc}") from exc

    from maafw_cli.maafw.controllers.dbg import connect_dbg as _connect

    controller = _connect(read_path, write_path, dbg_type_int, config_dict)
    if controller is None:
        raise DeviceConnectionError(
            f"Failed to connect DbgController (read={read_path}, write={write_path})."
        )

    result = {
        "type": "dbg",
        "read_path": read_path,
        "write_path": write_path,
        "dbg_type": dbg_type_int,
    }

    return result, controller


@service(
    name="connect_dbg",
    needs_session=False,
    human=lambda r: f"Connected DbgController (type={r.get('dbg_type', '?')}) as '{r.get('session', 'default')}'",
)
def do_connect_dbg(
    read_path: str,
    write_path: str,
    dbg_type: str = "carousel_image",
    config: str | None = None,
    session_name: str = "default",
) -> dict:
    """Connect a debug controller (direct-call fallback for DISPATCH table)."""
    result, _controller = _connect_dbg_inner(
        read_path, write_path, dbg_type, config,
    )
    result["session"] = session_name
    return result
