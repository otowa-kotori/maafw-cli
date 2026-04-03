"""
Custom Recognition & Action CLI commands — load, list, unload, clear.

Thin shells over ``services.custom``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.services.custom import (
    do_custom_load,
    do_custom_list,
    do_custom_unload,
    do_custom_clear,
)


@click.group()
def custom():
    """Manage custom recognitions and actions."""
    pass


@custom.command("load")
@click.argument("path", type=click.Path(exists=True))
@click.option("--reload", is_flag=True, default=False,
              help="Force re-import even if the script was loaded before.")
@pass_ctx
def custom_load(ctx: CliContext, path: str, reload: bool) -> None:
    """Load custom recognitions/actions from a Python script.

    PATH is a .py file containing CustomRecognition / CustomAction subclasses.
    """
    ctx.run(do_custom_load, path=path, reload=reload)


@custom.command("list")
@pass_ctx
def custom_list(ctx: CliContext) -> None:
    """List all registered custom recognitions and actions."""
    ctx.run(do_custom_list)


@custom.command("unload")
@click.argument("name")
@click.option("--type", "type_", type=click.Choice(["recognition", "action", "both"]),
              default="both", help="Which type to unload (default: both).")
@pass_ctx
def custom_unload(ctx: CliContext, name: str, type_: str) -> None:
    """Unregister a custom recognition/action by NAME."""
    ctx.run(do_custom_unload, name=name, type=type_)


@custom.command("clear")
@pass_ctx
def custom_clear(ctx: CliContext) -> None:
    """Clear all registered custom recognitions and actions."""
    ctx.run(do_custom_clear)
