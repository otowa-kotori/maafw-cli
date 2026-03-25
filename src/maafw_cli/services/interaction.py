"""
Interaction services — click, swipe, scroll, type, key.
"""
from __future__ import annotations

from maafw_cli.core.errors import ActionError
from maafw_cli.maafw.control import (
    click,
    swipe,
    scroll,
    input_text,
    press_key,
)
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service
from maafw_cli.core.keymap import resolve_keycode


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
