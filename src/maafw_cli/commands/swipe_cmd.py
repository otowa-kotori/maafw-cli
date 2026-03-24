"""
``maafw-cli swipe`` — swipe from one target to another.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_ACTION_FAILED


@click.command("swipe")
@click.argument("from_target", metavar="FROM")
@click.argument("to_target", metavar="TO")
@click.option("--duration", type=int, default=300, show_default=True, help="Swipe duration in milliseconds.")
@pass_ctx
def swipe_cmd(ctx: CliContext, from_target: str, to_target: str, duration: int) -> None:
    """Swipe from FROM to TO.

    FROM and TO can be a TextRef (e.g. t3) or coordinates (e.g. 452,387).

    \b
    Examples:
      maafw-cli swipe 100,800 100,200
      maafw-cli swipe 100,800 100,200 --duration 500
      maafw-cli swipe t1 t3
    """
    fmt = ctx.fmt

    # Resolve targets
    from maafw_cli.core.textref import TextRefStore
    from maafw_cli.core.session import textrefs_file
    from maafw_cli.core.target import parse_target, ResolvedTarget

    store = TextRefStore(textrefs_file())
    store.load()

    result1 = parse_target(from_target, store)
    if isinstance(result1, str):
        fmt.error(result1, exit_code=EXIT_ACTION_FAILED)
    result2 = parse_target(to_target, store)
    if isinstance(result2, str):
        fmt.error(result2, exit_code=EXIT_ACTION_FAILED)

    src: ResolvedTarget = result1  # type: ignore[assignment]
    dst: ResolvedTarget = result2  # type: ignore[assignment]
    fmt.info(
        f"Swiping ({src.x},{src.y}) -> ({dst.x},{dst.y}) "
        f"duration={duration}ms  [{src.source} -> {dst.source}]"
    )

    # Reconnect and swipe
    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    from maafw_cli.maafw.control import swipe as do_swipe

    ok = do_swipe(controller, src.x, src.y, dst.x, dst.y, duration)
    if not ok:
        fmt.error("Swipe failed.", exit_code=EXIT_ACTION_FAILED)

    fmt.success(
        {
            "action": "swipe",
            "x1": src.x, "y1": src.y,
            "x2": dst.x, "y2": dst.y,
            "duration": duration,
            "from_source": src.source,
            "to_source": dst.source,
        },
        human=f"Swiped ({src.x},{src.y}) -> ({dst.x},{dst.y})",
    )
