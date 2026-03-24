"""
Root CLI group and global options (--json, --quiet).

All sub-commands are registered here.
"""
from __future__ import annotations


import click

from maafw_cli import __version__
from maafw_cli.core.log import setup_logging
from maafw_cli.core.output import OutputFormatter


# ── shared context ──────────────────────────────────────────────

class CliContext:
    """Carries global state through Click's context."""

    def __init__(self, *, json_mode: bool = False, quiet: bool = False, verbose: bool = False):
        self.fmt = OutputFormatter(json_mode=json_mode, quiet=quiet)
        self.verbose = verbose


pass_ctx = click.make_pass_decorator(CliContext, ensure=True)


# ── root group ──────────────────────────────────────────────────

@click.group()
@click.version_option(version=__version__, prog_name="maafw-cli")
@click.option("--json", "json_mode", is_flag=True, default=False, help="Output strict JSON to stdout.")
@click.option("--quiet", is_flag=True, default=False, help="Suppress non-error output.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show detailed timing and debug info.")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, quiet: bool, verbose: bool) -> None:
    """maafw-cli — MaaFramework command-line interface."""
    ctx.ensure_object(dict)
    setup_logging(verbose=verbose, quiet=quiet)
    ctx.obj = CliContext(json_mode=json_mode, quiet=quiet, verbose=verbose)


# ── exit codes ──────────────────────────────────────────────────
# 0 = success
# 1 = action failed
# 2 = recognition failed
# 3 = connection error

EXIT_SUCCESS = 0
EXIT_ACTION_FAILED = 1
EXIT_RECOGNITION_FAILED = 2
EXIT_CONNECTION_ERROR = 3


# ── import sub-commands to register them ────────────────────────

from maafw_cli.commands.device import device  # noqa: E402
from maafw_cli.commands.connect import connect  # noqa: E402
from maafw_cli.commands.ocr import ocr  # noqa: E402
from maafw_cli.commands.screenshot import screenshot  # noqa: E402
from maafw_cli.commands.click_cmd import click_cmd  # noqa: E402

cli.add_command(device)
cli.add_command(connect)
cli.add_command(ocr, name="ocr")
cli.add_command(screenshot, name="screenshot")
cli.add_command(click_cmd, name="click")
