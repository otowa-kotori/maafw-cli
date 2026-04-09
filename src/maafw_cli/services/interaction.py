"""
Interaction services — click, swipe, scroll, type, key, longpress,
startapp/stopapp, shell, touch-down/move/up, key-down/up, mousemove,
and standalone custom actions.
"""
from __future__ import annotations

import json
from typing import Any

from maafw_cli.core.errors import ActionError
from maafw_cli.maafw.control import (

    click,
    swipe,
    scroll,
    input_text,
    press_key,
    long_press,
    touch_down,
    touch_move,
    touch_up,
    key_down,
    key_up,
    start_app,
    stop_app,
    run_shell,
    relative_move,
)
from maafw_cli.maafw.action import run_custom_action as execute_custom_action
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service
from maafw_cli.core.keymap import resolve_keycode


def _parse_kv_params(params: list[str] | tuple[str, ...] | None) -> dict[str, str]:
    if not params:
        return {}

    result: dict[str, str] = {}
    for token in params:
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


def _parse_rect(raw: str, *, field_name: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ActionError(f"Invalid {field_name} '{raw}'. Expected format: x,y,w,h")
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise ActionError(f"Invalid {field_name} '{raw}'. All values must be integers.")


def _parse_custom_action_param(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _resolve_custom_action_box(ctx: ServiceContext, target: str | None) -> tuple[tuple[int, int, int, int] | None, str | None]:
    if target is None:
        return None, None
    resolved = ctx.resolve_target(target)
    return resolved.box, resolved.source


@service(human=lambda r: f"Clicked ({r['x']}, {r['y']})")

def do_click(ctx: ServiceContext, target: str) -> dict:
    resolved = ctx.resolve_target(target)
    ok = click(ctx.controller, resolved.x, resolved.y)
    if not ok:
        raise ActionError("Click failed.")
    return {"action": "click", "x": resolved.x, "y": resolved.y, "source": resolved.source}


@service(human=lambda r: f"Swiped ({r['x1']},{r['y1']}) -> ({r['x2']},{r['y2']})")
def do_swipe(
    ctx: ServiceContext, from_target: str, to_target: str, duration: int = 300
) -> dict:
    if duration <= 0:
        raise ActionError(f"Duration must be positive, got {duration}.")
    src = ctx.resolve_target(from_target)
    dst = ctx.resolve_target(to_target)
    ok = swipe(ctx.controller, src.x, src.y, dst.x, dst.y, duration)
    if not ok:
        raise ActionError("Swipe failed.")
    return {
        "action": "swipe",
        "x1": src.x, "y1": src.y,
        "x2": dst.x, "y2": dst.y,
        "duration": duration,
        "from_source": src.source,
        "to_source": dst.source,
    }


@service(human=lambda r: f"Scrolled dx={r['dx']}, dy={r['dy']}")
def do_scroll(ctx: ServiceContext, dx: int, dy: int) -> dict:
    if ctx.session_type != "win32":
        raise ActionError("Scroll is only supported on PC/Win32 sessions.")
    if not isinstance(dx, int) or not isinstance(dy, int):
        raise ActionError(f"Scroll dx/dy must be integers, got dx={dx!r}, dy={dy!r}.")
    ok = scroll(ctx.controller, dx, dy)
    if not ok:
        raise ActionError("Scroll failed.")
    return {"action": "scroll", "dx": dx, "dy": dy}


@service(human=lambda r: f"Typed: {r['text']!r}")
def do_type(ctx: ServiceContext, text: str) -> dict:
    ok = input_text(ctx.controller, text)
    if not ok:
        raise ActionError("Type failed.")
    return {"action": "type", "text": text}


@service(human=lambda r: f"Pressed key {r['name']} -> {r['keycode']} (0x{r['keycode']:02X}) [{r['session_type']}]")
def do_key(ctx: ServiceContext, keycode: str) -> dict:
    code = resolve_keycode(keycode, ctx.session_type)
    if code is None:
        platform = "Android" if ctx.session_type == "adb" else "Win32"
        raise ActionError(
            f"Unknown key '{keycode}' for {platform}. "
            f"Use a name (enter, tab, back, f1, ...) or an integer."
        )
    ok = press_key(ctx.controller, code)
    if not ok:
        raise ActionError("Key press failed.")
    return {
        "action": "key",
        "keycode": code,
        "keycode_hex": f"0x{code:02X}",
        "name": keycode,
        "session_type": ctx.session_type,
    }


@service(human=lambda r: f"Long-pressed ({r['x']}, {r['y']}) for {r['duration']}ms")
def do_longpress(ctx: ServiceContext, target: str, duration: int = 1000) -> dict:
    if duration <= 0:
        raise ActionError(f"Duration must be positive, got {duration}.")
    resolved = ctx.resolve_target(target)
    ok = long_press(ctx.controller, resolved.x, resolved.y, duration)
    if not ok:
        raise ActionError("Long press failed.")
    return {
        "action": "longpress",
        "x": resolved.x, "y": resolved.y,
        "duration": duration,
        "source": resolved.source,
    }


@service(human=lambda r: f"Started app: {r['intent']}")
def do_startapp(ctx: ServiceContext, intent: str) -> dict:
    ok = start_app(ctx.controller, intent)
    if not ok:
        raise ActionError("Start app failed.")
    return {"action": "startapp", "intent": intent}


@service(human=lambda r: f"Stopped app: {r['intent']}")
def do_stopapp(ctx: ServiceContext, intent: str) -> dict:
    ok = stop_app(ctx.controller, intent)
    if not ok:
        raise ActionError("Stop app failed.")
    return {"action": "stopapp", "intent": intent}


@service(human=lambda r: r["output"] if r["output"] else "(no output)")
def do_shell(ctx: ServiceContext, cmd: str, timeout: int = 20000) -> dict:
    output = run_shell(ctx.controller, cmd, timeout)
    return {"action": "shell", "cmd": cmd, "timeout": timeout, "output": output}


@service(human=lambda r: f"Touch down ({r['x']}, {r['y']}) contact={r['contact']}")
def do_touch_down(
    ctx: ServiceContext, target: str, contact: int = 0, pressure: int = 1
) -> dict:
    resolved = ctx.resolve_target(target)
    ok = touch_down(ctx.controller, resolved.x, resolved.y, contact, pressure)
    if not ok:
        raise ActionError("Touch down failed.")
    return {
        "action": "touch_down",
        "x": resolved.x, "y": resolved.y,
        "contact": contact, "pressure": pressure,
        "source": resolved.source,
    }


@service(human=lambda r: f"Touch move ({r['x']}, {r['y']}) contact={r['contact']}")
def do_touch_move(
    ctx: ServiceContext, target: str, contact: int = 0, pressure: int = 1
) -> dict:
    resolved = ctx.resolve_target(target)
    ok = touch_move(ctx.controller, resolved.x, resolved.y, contact, pressure)
    if not ok:
        raise ActionError("Touch move failed.")
    return {
        "action": "touch_move",
        "x": resolved.x, "y": resolved.y,
        "contact": contact, "pressure": pressure,
        "source": resolved.source,
    }


@service(human=lambda r: f"Touch up contact={r['contact']}")
def do_touch_up(ctx: ServiceContext, contact: int = 0) -> dict:
    ok = touch_up(ctx.controller, contact)
    if not ok:
        raise ActionError("Touch up failed.")
    return {"action": "touch_up", "contact": contact}


@service(human=lambda r: f"Key down {r['name']} -> {r['keycode']} [{r['session_type']}]")
def do_key_down(ctx: ServiceContext, keycode: str) -> dict:
    code = resolve_keycode(keycode, ctx.session_type)
    if code is None:
        platform = "Android" if ctx.session_type == "adb" else "Win32"
        raise ActionError(
            f"Unknown key '{keycode}' for {platform}. "
            f"Use a name (enter, tab, back, f1, ...) or an integer."
        )
    ok = key_down(ctx.controller, code)
    if not ok:
        raise ActionError("Key down failed.")
    return {
        "action": "key_down",
        "keycode": code,
        "keycode_hex": f"0x{code:02X}",
        "name": keycode,
        "session_type": ctx.session_type,
    }


@service(human=lambda r: f"Key up {r['name']} -> {r['keycode']} [{r['session_type']}]")
def do_key_up(ctx: ServiceContext, keycode: str) -> dict:
    code = resolve_keycode(keycode, ctx.session_type)
    if code is None:
        platform = "Android" if ctx.session_type == "adb" else "Win32"
        raise ActionError(
            f"Unknown key '{keycode}' for {platform}. "
            f"Use a name (enter, tab, back, f1, ...) or an integer."
        )
    ok = key_up(ctx.controller, code)
    if not ok:
        raise ActionError("Key up failed.")
    return {
        "action": "key_up",
        "keycode": code,
        "keycode_hex": f"0x{code:02X}",
        "name": keycode,
        "session_type": ctx.session_type,
    }


def _human_custom_action(r: dict) -> str:
    target_source = r.get("target_source")
    box = r.get("box")
    suffix = f" target={target_source} box={tuple(box)}" if target_source and box else ""
    return f"Custom action '{r['custom_action']}' succeeded.{suffix}"


@service(name="custom_action", human=_human_custom_action)
def do_custom_action(
    ctx: ServiceContext,
    name: str | None = None,
    params: list[str] | tuple[str, ...] | None = None,
    raw: str | None = None,
    target: str | None = None,
    reco_detail: str | None = None,
) -> dict:
    parsed_params = _parse_kv_params(params) if raw is None else {}
    target_source: str | None = None

    if raw is not None:
        target_box = None
        try:
            raw_data = json.loads(raw)

        except json.JSONDecodeError as exc:
            raise ActionError(f"Invalid JSON: {exc}")
        if not isinstance(raw_data, dict):
            raise ActionError("Raw JSON must be an object.")

        raw_name = raw_data.pop("custom_action", None)
        if name is None:
            name = raw_name
        elif raw_name is not None and raw_name != name:
            raise ActionError(
                f"Custom action mismatch: positional name '{name}' != raw custom_action '{raw_name}'."
            )

        raw_target = raw_data.pop("target", None)
        if target is None and isinstance(raw_target, str):
            target = raw_target
        elif raw_target is not None and not isinstance(raw_target, str):
            if isinstance(raw_target, (list, tuple)) and len(raw_target) in (2, 4):
                if len(raw_target) == 2:
                    target_box = (int(raw_target[0]), int(raw_target[1]), 0, 0)
                    target_source = f"point:{raw_target[0]},{raw_target[1]}"
                else:
                    target_box = tuple(int(v) for v in raw_target)
                    target_source = f"box:{','.join(str(int(v)) for v in raw_target)}"
            elif raw_target in (None, True, False):
                target_box = None
            else:
                raise ActionError("Raw JSON field 'target' must be a string, [x,y], or [x,y,w,h].")
        else:
            target_box = None

        raw_param = raw_data.pop("custom_action_param", None)
        raw_target_offset = raw_data.pop("target_offset", (0, 0, 0, 0))
        if isinstance(raw_target_offset, str):
            target_offset = _parse_rect(raw_target_offset, field_name="target_offset")
        elif isinstance(raw_target_offset, (list, tuple)) and len(raw_target_offset) == 4:
            target_offset = tuple(int(v) for v in raw_target_offset)
        else:
            raise ActionError("Raw JSON field 'target_offset' must be x,y,w,h or [x,y,w,h].")

        if reco_detail is None:
            raw_reco_detail = raw_data.pop("reco_detail", "")
            reco_detail = raw_reco_detail if isinstance(raw_reco_detail, str) else json.dumps(raw_reco_detail, ensure_ascii=False)
        custom_action_param = raw_param
    else:
        if name is None:
            raise ActionError("Custom action name is required. Use: action custom <name> [params...] or --raw '{...}'")
        target_box = None
        raw_param = parsed_params.get("custom_action_param")
        custom_action_param = _parse_custom_action_param(raw_param) if raw_param is not None else None
        raw_target_offset = parsed_params.get("target_offset")
        target_offset = _parse_rect(raw_target_offset, field_name="target_offset") if raw_target_offset else (0, 0, 0, 0)

    if name is None:
        raise ActionError("Custom action name is required.")

    resolved_box, resolved_source = _resolve_custom_action_box(ctx, target)
    if resolved_box is not None:
        target_box = resolved_box
        target_source = resolved_source

    execute_custom_action(
        ctx.session,
        name,
        custom_action_param=custom_action_param,
        target_offset=target_offset,
        box=target_box,
        reco_detail=reco_detail or "",
    )

    result: dict[str, Any] = {
        "action": "custom",
        "custom_action": name,
        "success": True,
        "custom_action_param": custom_action_param,
        "target_offset": list(target_offset),
        "reco_detail": reco_detail or "",
    }
    if target_box is not None:
        result["box"] = list(target_box)
    if target_source is not None:
        result["target_source"] = target_source
    return result


@service(human=lambda r: f"Mouse moved ({r['dx']}, {r['dy']})")
def do_mousemove(ctx: ServiceContext, dx: int, dy: int) -> dict:
    if ctx.session_type != "win32":
        raise ActionError("Mouse move is only supported on PC/Win32 sessions.")
    ok = relative_move(ctx.controller, dx, dy)
    if not ok:
        raise ActionError("Mouse move failed.")
    return {"action": "mousemove", "dx": dx, "dy": dy}

