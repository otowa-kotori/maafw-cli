"""
``maafw-cli type`` — input text into the focused control.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_ACTION_FAILED


@click.command("type")
@click.argument("text")
@pass_ctx
def type_cmd(ctx: CliContext, text: str) -> None:
    """Type TEXT into the focused control.

    \b
    Examples:
      maafw-cli type "Hello World"
      maafw-cli type 你好
    """
    fmt = ctx.fmt
    fmt.info(f"Typing: {text!r}")

    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    from maafw_cli.maafw.control import input_text

    ok = input_text(controller, text)
    if not ok:
        fmt.error("Type failed.", exit_code=EXIT_ACTION_FAILED)

    fmt.success(
        {"action": "type", "text": text},
        human=f"Typed: {text!r}",
    )
