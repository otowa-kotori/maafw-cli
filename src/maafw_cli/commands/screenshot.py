"""
``maafw-cli screenshot`` — capture device screen.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_ACTION_FAILED


@click.command()
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path. Auto-generated if omitted.")
@pass_ctx
def screenshot(ctx: CliContext, output: str | None) -> None:
    """Take a screenshot of the connected device screen."""
    fmt = ctx.fmt

    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    from maafw_cli.maafw.vision import screencap_to_file

    path = screencap_to_file(controller, output)
    if path is None:
        fmt.error("Screenshot failed.", exit_code=EXIT_ACTION_FAILED)

    fmt.success(
        {"path": str(path.absolute())},
        human=f"Saved: {path.absolute()}",
    )
