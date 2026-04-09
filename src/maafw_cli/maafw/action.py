"""Standalone action execution helpers via temporary MaaFramework pipeline nodes."""
from __future__ import annotations

import logging
from typing import Any

from maafw_cli.core.errors import ActionError
from maafw_cli.core.log import Timer
from maafw_cli.core.session import Session
from maafw_cli.maafw.pipeline import run_pipeline

_log = logging.getLogger("maafw_cli.maafw.action")

_TEMP_CUSTOM_ACTION_ENTRY = "__maafw_cli_direct_custom_action__"


def _normalize_box(box: tuple[int, int, int, int] | list[int] | None) -> tuple[int, int, int, int]:

    if box is None:
        return (0, 0, 0, 0)
    return _normalize_rect(box)


def _normalize_rect(rect: tuple[int, int, int, int] | list[int]) -> tuple[int, int, int, int]:
    values = [int(v) for v in rect]
    if len(values) != 4:
        raise ActionError(f"Expected rect with 4 integers, got {values!r}.")
    return (values[0], values[1], values[2], values[3])



def _build_directhit_custom_action_node(
    name: str,
    *,
    box: tuple[int, int, int, int],
    custom_action_param: Any = None,
    target_offset: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "recognition": "DirectHit",
        "roi": list(box),
        "action": "Custom",
        "custom_action": name,
        "next": [],
    }
    if custom_action_param is not None:
        node["custom_action_param"] = custom_action_param
    if target_offset != (0, 0, 0, 0):
        node["target_offset"] = list(target_offset)
    return node


def run_custom_action(
    session: Session,
    name: str,
    *,
    custom_action_param: Any = None,
    target_offset: tuple[int, int, int, int] = (0, 0, 0, 0),
    box: tuple[int, int, int, int] | list[int] | None = None,
    reco_detail: str = "",
) -> bool:
    """Execute a standalone ``CustomAction`` via a temporary ``DirectHit`` pipeline node."""
    resolved_box = _normalize_box(box)
    resolved_target_offset = _normalize_rect(target_offset)
    if reco_detail:
        _log.debug(
            "Standalone custom action ignores provided reco_detail when using DirectHit temp pipeline: %r",
            reco_detail,
        )

    pipeline_override = {
        _TEMP_CUSTOM_ACTION_ENTRY: _build_directhit_custom_action_node(
            name,
            box=resolved_box,
            custom_action_param=custom_action_param,
            target_offset=resolved_target_offset,
        )
    }

    with Timer(f"custom action {name}", log=_log):
        detail = run_pipeline(session, _TEMP_CUSTOM_ACTION_ENTRY, pipeline_override)

    if not getattr(detail.status, "succeeded", False):
        raise ActionError(f"Custom action '{name}' failed.")

    first_node = detail.nodes[0] if detail.nodes else None
    if first_node is None or first_node.action is None or not first_node.action.success:
        raise ActionError(f"Custom action '{name}' failed.")

    return True

