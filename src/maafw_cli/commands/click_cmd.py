"""
``maafw-cli click`` — click on a target (TextRef or coordinates).
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_ACTION_FAILED


@click.command("click")
@click.argument("target")
@click.option("--long", "long_press", type=int, default=None,
              help="Long-press duration in ms.")
@pass_ctx
def click_cmd(ctx: CliContext, target: str, long_press: int | None) -> None:
    """Click on a target.

    TARGET can be a TextRef (e.g. t3) or coordinates (e.g. 452,387).
    """
    fmt = ctx.fmt
    duration = long_press if long_press is not None else 50

    # Resolve target
    from maafw_cli.core.textref import TextRefStore
    from maafw_cli.core.session import textrefs_file
    from maafw_cli.core.target import parse_target, ResolvedTarget

    store = TextRefStore(textrefs_file())
    store.load()

    result = parse_target(target, store)
    if isinstance(result, str):
        fmt.error(result, exit_code=EXIT_ACTION_FAILED)

    resolved: ResolvedTarget = result
    fmt.info(f"Clicking ({resolved.x}, {resolved.y}) ← {resolved.source}")

    # Reconnect and click
    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    from maafw_cli.maafw.control import click as do_click

    ok = do_click(controller, resolved.x, resolved.y, duration=duration)
    if not ok:
        fmt.error("Click failed.", exit_code=EXIT_ACTION_FAILED)

    fmt.success(
        {"action": "click", "x": resolved.x, "y": resolved.y, "source": resolved.source},
        human=f"Clicked ({resolved.x}, {resolved.y})",
    )
