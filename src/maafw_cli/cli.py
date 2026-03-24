"""
Root CLI group and global options (--json, --quiet).

All sub-commands are registered here.
"""
from __future__ import annotations

from typing import Callable

import click

from maafw_cli import __version__
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.log import setup_logging
from maafw_cli.core.output import OutputFormatter


# ── shared context ──────────────────────────────────────────────

class CliContext:
    """Carries global state through Click's context."""

    def __init__(self, *, json_mode: bool = False, quiet: bool = False, verbose: bool = False):
        self.fmt = OutputFormatter(json_mode=json_mode, quiet=quiet)
        self.verbose = verbose

    def _make_service_context(self):
        """Build a :class:`ServiceContext` for the current session."""
        from maafw_cli.core.reconnect import reconnect
        from maafw_cli.core.session import load_session, textrefs_file
        from maafw_cli.services.context import ServiceContext

        session = load_session()
        session_type = session.type if session else "win32"

        return ServiceContext(
            get_controller=lambda: reconnect(self.fmt),
            textrefs_path=textrefs_file(),
            session_type=session_type,
        )

    def run(self, service_fn: Callable, **kwargs) -> dict:
        """Call a service function with automatic context injection and error handling.

        Builds a :class:`ServiceContext`, calls *service_fn(ctx, **kwargs)*,
        catches :class:`MaafwError` → ``fmt.error()``, and on success routes
        the result through ``fmt.success()`` using the service's ``human_fmt``.
        """
        svc_ctx = self._make_service_context()
        try:
            result = service_fn(svc_ctx, **kwargs)
        except MaafwError as e:
            self.fmt.error(str(e), exit_code=e.exit_code)
            return {}  # unreachable — fmt.error exits

        human_fn = getattr(service_fn, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)
        return result


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


# ── exit codes (kept for backward compat imports) ────────────────
EXIT_SUCCESS = 0
EXIT_ACTION_FAILED = 1
EXIT_RECOGNITION_FAILED = 2
EXIT_CONNECTION_ERROR = 3


# ── import sub-commands to register them ────────────────────────

from maafw_cli.commands.connection import device, connect  # noqa: E402
from maafw_cli.commands.vision import ocr, screenshot  # noqa: E402
from maafw_cli.commands.interaction import click_cmd, swipe_cmd, scroll_cmd, type_cmd, key_cmd  # noqa: E402
from maafw_cli.commands.repl_cmd import repl_cmd  # noqa: E402

cli.add_command(device)
cli.add_command(connect)
cli.add_command(ocr, name="ocr")
cli.add_command(screenshot, name="screenshot")
cli.add_command(click_cmd, name="click")
cli.add_command(swipe_cmd, name="swipe")
cli.add_command(scroll_cmd, name="scroll")
cli.add_command(type_cmd, name="type")
cli.add_command(key_cmd, name="key")
cli.add_command(repl_cmd, name="repl")
