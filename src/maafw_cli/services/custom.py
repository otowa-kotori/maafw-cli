"""
Custom Recognition & Action services — load, list, unload, clear.

User Python scripts containing ``CustomRecognition`` / ``CustomAction``
subclasses are loaded via :mod:`maafw_cli.core.script_loader` and
registered on the session's Resource.
"""
from __future__ import annotations

import logging

from maafw_cli.core.errors import ActionError
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service

_log = logging.getLogger("maafw_cli.services.custom")


def _human_load(r: dict) -> str:
    recos = r.get("recognitions", [])
    acts = r.get("actions", [])
    parts: list[str] = []
    if recos:
        parts.append(f"recognitions: {', '.join(recos)}")
    if acts:
        parts.append(f"actions: {', '.join(acts)}")
    return f"Loaded {' | '.join(parts)}" if parts else "No custom classes found."


def _human_list(r: dict) -> str:
    recos = r.get("recognitions", [])
    acts = r.get("actions", [])
    lines: list[str] = []
    if recos:
        lines.append(f"Recognitions: {', '.join(recos)}")
    if acts:
        lines.append(f"Actions: {', '.join(acts)}")
    return "\n".join(lines) if lines else "(no custom registered)"


@service(name="custom_load", human=_human_load)
def do_custom_load(ctx: ServiceContext, path: str, reload: bool = False) -> dict:
    """Load a Python script and register discovered custom classes."""
    from maafw_cli.core.script_loader import load_script

    try:
        result = load_script(path, reload=reload)
    except FileNotFoundError as exc:
        raise ActionError(str(exc)) from exc
    except ValueError as exc:
        raise ActionError(str(exc)) from exc
    except ImportError as exc:
        raise ActionError(str(exc)) from exc

    ss = ctx.session

    # Register recognitions
    reco_names: list[str] = []
    for name, instance in result.recognitions.items():
        ok = ss.register_custom_recognition(name, instance)
        if not ok:
            raise ActionError(f"Failed to register recognition: {name}")
        reco_names.append(name)

    # Register actions
    action_names: list[str] = []
    for name, instance in result.actions.items():
        ok = ss.register_custom_action(name, instance)
        if not ok:
            raise ActionError(f"Failed to register action: {name}")
        action_names.append(name)

    return {
        "path": result.path,
        "recognitions": reco_names,
        "actions": action_names,
    }


@service(name="custom_list", human=_human_list)
def do_custom_list(ctx: ServiceContext) -> dict:
    """List all registered custom recognitions and actions."""
    ss = ctx.session
    return {
        "recognitions": ss.list_custom_recognition(),
        "actions": ss.list_custom_action(),
    }


@service(
    name="custom_unload",
    human=lambda r: f"Unloaded: {r['name']} ({r['type']})",
)
def do_custom_unload(
    ctx: ServiceContext,
    name: str,
    type: str = "both",
) -> dict:
    """Unregister a custom recognition/action by name.

    *type* is ``"recognition"``, ``"action"``, or ``"both"`` (default).
    """
    ss = ctx.session
    removed_reco = False
    removed_action = False

    if type in ("recognition", "both"):
        removed_reco = ss.unregister_custom_recognition(name)

    if type in ("action", "both"):
        removed_action = ss.unregister_custom_action(name)

    if not removed_reco and not removed_action:
        raise ActionError(f"Custom '{name}' not found (type={type}).")

    return {"name": name, "type": type, "removed_recognition": removed_reco, "removed_action": removed_action}


@service(
    name="custom_clear",
    human=lambda r: "Cleared all custom recognitions and actions.",
)
def do_custom_clear(ctx: ServiceContext) -> dict:
    """Clear all registered custom recognitions and actions."""
    ss = ctx.session
    ss.clear_custom_recognition()
    ss.clear_custom_action()
    return {"cleared": True}
