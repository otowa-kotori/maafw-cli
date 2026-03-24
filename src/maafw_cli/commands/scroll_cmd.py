"""
``maafw-cli scroll`` — scroll by (dx, dy).
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_ACTION_FAILED


@click.command("scroll", context_settings={"ignore_unknown_options": True})
@click.argument("dx", type=int)
@click.argument("dy", type=int)
@pass_ctx
def scroll_cmd(ctx: CliContext, dx: int, dy: int) -> None:
    """Scroll by DX (horizontal) and DY (vertical).

    Use multiples of 120 (WHEEL_DELTA) for best compatibility.
    Positive DY scrolls up, negative DY scrolls down.

    \b
    Examples:
      maafw-cli scroll 0 -360      # scroll down 3 notches
      maafw-cli scroll 0 360       # scroll up 3 notches
      maafw-cli scroll 120 0       # scroll right 1 notch
    """
    fmt = ctx.fmt
    fmt.info(f"Scrolling dx={dx}, dy={dy}")

    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    from maafw_cli.maafw.control import scroll as do_scroll

    ok = do_scroll(controller, dx, dy)
    if not ok:
        fmt.error("Scroll failed.", exit_code=EXIT_ACTION_FAILED)

    fmt.success(
        {"action": "scroll", "dx": dx, "dy": dy},
        human=f"Scrolled dx={dx}, dy={dy}",
    )
