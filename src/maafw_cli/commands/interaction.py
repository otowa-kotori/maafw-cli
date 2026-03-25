"""
Interaction CLI commands — click, swipe, scroll, type, key.

Thin shells over ``services.interaction``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.services.interaction import do_click, do_swipe, do_scroll, do_type, do_key


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
