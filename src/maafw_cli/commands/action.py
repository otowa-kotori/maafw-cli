"""
Action CLI commands — all device operations under ``action`` group.

High-frequency commands (click/swipe/scroll/type/key) are also
registered as top-level aliases in ``cli.py``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.services.interaction import (
    do_click, do_swipe, do_scroll, do_type, do_key,
    do_longpress, do_startapp, do_stopapp, do_shell,
    do_touch_down, do_touch_move, do_touch_up,
    do_key_down, do_key_up, do_mousemove,
)


@click.group("action")
def action() -> None:
    """Device action commands (click, swipe, type, key, longpress, ...)."""


# ── existing 5 commands ─────────────────────────────────────────


@click.command("click")
@click.argument("target")
@pass_ctx
def click_cmd(ctx: CliContext, target: str) -> None:
    """Click on a target.

    TARGET can be an Element ref (e.g. e3) or coordinates (e.g. 452,387).
    """
    ctx.run(do_click, target=target)


@click.command("swipe")
@click.argument("from_target", metavar="FROM")
@click.argument("to_target", metavar="TO")
@click.option("--duration", type=int, default=300, show_default=True,
              help="Swipe duration in milliseconds.")
@pass_ctx
def swipe_cmd(ctx: CliContext, from_target: str, to_target: str, duration: int) -> None:
    """Swipe from FROM to TO.

    FROM and TO can be an Element ref (e.g. e3) or coordinates (e.g. 452,387).

    \b
    Examples:
      maafw-cli swipe 100,800 100,200
      maafw-cli swipe 100,800 100,200 --duration 500
      maafw-cli swipe e1 e3
    """
    ctx.run(do_swipe, from_target=from_target, to_target=to_target, duration=duration)


@click.command("scroll", context_settings={"ignore_unknown_options": True})
@click.argument("dx", type=int)
@click.argument("dy", type=int)
@pass_ctx
def scroll_cmd(ctx: CliContext, dx: int, dy: int) -> None:
    """Scroll by DX (horizontal) and DY (vertical).  [PC/Win32 only]

    Use multiples of 120 (WHEEL_DELTA) for best compatibility.

    \b
    Examples:
      maafw-cli scroll 0 -360
      maafw-cli scroll 0 360
    """
    ctx.run(do_scroll, dx=dx, dy=dy)


@click.command("type")
@click.argument("text")
@pass_ctx
def type_cmd(ctx: CliContext, text: str) -> None:
    """Type TEXT into the focused control.

    \b
    Examples:
      maafw-cli type "Hello World"
    """
    ctx.run(do_type, text=text)


@click.command("key")
@click.argument("keycode")
@pass_ctx
def key_cmd(ctx: CliContext, keycode: str) -> None:
    """Press a virtual key.

    KEYCODE can be a name (enter, tab, esc, back, f1-f12, ...) or an
    integer (decimal or 0x hex).  Named keys are automatically mapped
    to the correct code for the current session type (ADB or Win32).

    \b
    Examples:
      maafw-cli key enter
      maafw-cli key back
      maafw-cli key f5
      maafw-cli key 66
    """
    ctx.run(do_key, keycode=keycode)


# ── new commands ────────────────────────────────────────────────


@click.command("longpress")
@click.argument("target")
@click.option("--duration", type=int, default=1000, show_default=True,
              help="Long-press duration in milliseconds.")
@pass_ctx
def longpress_cmd(ctx: CliContext, target: str, duration: int) -> None:
    """Long-press on a target.

    TARGET can be an Element ref (e.g. e3) or coordinates (e.g. 452,387).

    \b
    Examples:
      maafw-cli action longpress e1
      maafw-cli action longpress 200,300 --duration 2000
    """
    ctx.run(do_longpress, target=target, duration=duration)


@click.command("startapp")
@click.argument("intent")
@pass_ctx
def startapp_cmd(ctx: CliContext, intent: str) -> None:
    """Start an app on the device (ADB).

    INTENT is the Android intent or package name.

    \b
    Examples:
      maafw-cli action startapp com.example.app/.MainActivity
    """
    ctx.run(do_startapp, intent=intent)


@click.command("stopapp")
@click.argument("intent")
@pass_ctx
def stopapp_cmd(ctx: CliContext, intent: str) -> None:
    """Stop an app on the device (ADB).

    INTENT is the Android package name.

    \b
    Examples:
      maafw-cli action stopapp com.example.app
    """
    ctx.run(do_stopapp, intent=intent)


@click.command("shell")
@click.argument("cmd")
@click.option("--timeout", type=int, default=20000, show_default=True,
              help="Command timeout in milliseconds.")
@pass_ctx
def shell_cmd(ctx: CliContext, cmd: str, timeout: int) -> None:
    """Run a shell command on the device.

    \b
    Examples:
      maafw-cli action shell "ls /sdcard"
      maafw-cli action shell "dumpsys activity" --timeout 30000
    """
    ctx.run(do_shell, cmd=cmd, timeout=timeout)


@click.command("touch-down")
@click.argument("target")
@click.option("--contact", type=int, default=0, show_default=True,
              help="Touch contact ID (for multi-touch).")
@click.option("--pressure", type=int, default=1, show_default=True,
              help="Touch pressure.")
@pass_ctx
def touch_down_cmd(ctx: CliContext, target: str, contact: int, pressure: int) -> None:
    """Touch down (finger press) at a target.

    TARGET can be an Element ref (e.g. e3) or coordinates (e.g. 452,387).

    \b
    Examples:
      maafw-cli action touch-down 200,300
      maafw-cli action touch-down 200,300 --contact 1
    """
    ctx.run(do_touch_down, target=target, contact=contact, pressure=pressure)


@click.command("touch-move")
@click.argument("target")
@click.option("--contact", type=int, default=0, show_default=True,
              help="Touch contact ID.")
@click.option("--pressure", type=int, default=1, show_default=True,
              help="Touch pressure.")
@pass_ctx
def touch_move_cmd(ctx: CliContext, target: str, contact: int, pressure: int) -> None:
    """Move a pressed touch point to a target.

    TARGET can be an Element ref (e.g. e3) or coordinates (e.g. 452,387).

    \b
    Examples:
      maafw-cli action touch-move 400,500
    """
    ctx.run(do_touch_move, target=target, contact=contact, pressure=pressure)


@click.command("touch-up")
@click.option("--contact", type=int, default=0, show_default=True,
              help="Touch contact ID.")
@pass_ctx
def touch_up_cmd(ctx: CliContext, contact: int) -> None:
    """Lift a touch point (finger release).

    \b
    Examples:
      maafw-cli action touch-up
      maafw-cli action touch-up --contact 1
    """
    ctx.run(do_touch_up, contact=contact)


@click.command("key-down")
@click.argument("keycode")
@pass_ctx
def key_down_cmd(ctx: CliContext, keycode: str) -> None:
    """Press a key down (without releasing).

    KEYCODE follows the same rules as ``key``.

    \b
    Examples:
      maafw-cli action key-down shift
      maafw-cli action key-down ctrl
    """
    ctx.run(do_key_down, keycode=keycode)


@click.command("key-up")
@click.argument("keycode")
@pass_ctx
def key_up_cmd(ctx: CliContext, keycode: str) -> None:
    """Release a previously pressed key.

    KEYCODE follows the same rules as ``key``.

    \b
    Examples:
      maafw-cli action key-up shift
      maafw-cli action key-up ctrl
    """
    ctx.run(do_key_up, keycode=keycode)


@click.command("mousemove")
@click.argument("dx", type=int)
@click.argument("dy", type=int)
@pass_ctx
def mousemove_cmd(ctx: CliContext, dx: int, dy: int) -> None:
    """Move mouse cursor relatively.  [PC/Win32 only]

    \b
    Examples:
      maafw-cli action mousemove 100 -50
    """
    ctx.run(do_mousemove, dx=dx, dy=dy)


# ── register all sub-commands ────────────────────────────────────

action.add_command(click_cmd, "click")
action.add_command(swipe_cmd, "swipe")
action.add_command(scroll_cmd, "scroll")
action.add_command(type_cmd, "type")
action.add_command(key_cmd, "key")
action.add_command(longpress_cmd, "longpress")
action.add_command(startapp_cmd, "startapp")
action.add_command(stopapp_cmd, "stopapp")
action.add_command(shell_cmd, "shell")
action.add_command(touch_down_cmd, "touch-down")
action.add_command(touch_move_cmd, "touch-move")
action.add_command(touch_up_cmd, "touch-up")
action.add_command(key_down_cmd, "key-down")
action.add_command(key_up_cmd, "key-up")
action.add_command(mousemove_cmd, "mousemove")
