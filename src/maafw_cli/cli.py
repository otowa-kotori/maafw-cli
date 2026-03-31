"""
Root CLI group and global options (--json, --quiet, --on).

All sub-commands are registered here.
"""
from __future__ import annotations

import logging
from typing import Callable

import click

from maafw_cli import __version__
from maafw_cli.core.errors import MaafwError, VersionMismatchError
from maafw_cli.core.log import setup_logging
from maafw_cli.core.output import OutputFormatter

_log = logging.getLogger("maafw_cli.cli")


# ── GlobalOptionGroup ─────────────────────────────────────────


class GlobalOptionGroup(click.Group):
    """Allow global options (``--on``, ``--json``, etc.) at any position in argv.

    Standard Click requires group-level options before the sub-command name.
    This subclass extracts known global options from *anywhere* in the
    argument list and moves them to the front before Click parses.

    The ``--`` separator is respected: options after it are never extracted.
    """

    GLOBAL_FLAGS: frozenset[str] = frozenset({"--json", "--quiet", "-v", "--verbose"})
    GLOBAL_WITH_VALUE: frozenset[str] = frozenset({"--on"})

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        remaining: list[str] = []
        global_args: list[str] = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--":
                remaining.extend(args[i:])
                break
            elif arg in self.GLOBAL_FLAGS:
                global_args.append(arg)
                i += 1
            elif arg in self.GLOBAL_WITH_VALUE:
                if i + 1 < len(args):
                    global_args.extend([arg, args[i + 1]])
                    i += 2
                else:
                    # missing value — let Click report the error
                    global_args.append(arg)
                    i += 1
            else:
                remaining.append(arg)
                i += 1
        return super().parse_args(ctx, global_args + remaining)

    def invoke(self, ctx: click.Context) -> None:
        try:
            return super().invoke(ctx)
        except VersionMismatchError as e:
            click.echo(f"Error: {e}", err=True)
            ctx.exit(e.exit_code)


# ── action name reverse-lookup ─────────────────────────────────

def _get_action_name(fn: Callable) -> str | None:
    """Return the DISPATCH key for a service function."""
    return getattr(fn, "dispatch_key", None)


# ── shared context ──────────────────────────────────────────────

class CliContext:
    """Carries global state through Click's context.

    When *executor* is set (a :class:`LocalExecutor`), all service calls
    are dispatched in-process without daemon IPC.  This powers ``repl --local``.
    """

    def __init__(
        self,
        *,
        json_mode: bool = False,
        quiet: bool = False,
        verbose: bool = False,
        on: str | None = None,
        executor: object | None = None,
    ):
        self.fmt = OutputFormatter(json_mode=json_mode, quiet=quiet)
        self.verbose = verbose
        self.on = on          # --on <session>: target specific daemon session
        self.executor = executor  # None = daemon IPC, LocalExecutor = in-process

    def run(self, service_fn: Callable, **kwargs) -> dict:
        """Call a service function via daemon IPC or local executor.

        Automatically handles ``needs_session`` — services that don't need
        a session (e.g. ``device_list``) are still routed through the daemon.
        """
        if self.executor is not None:
            return self._run_local(service_fn, **kwargs)

        needs_session = getattr(service_fn, "needs_session", True)

        if not needs_session:
            return self._run_no_session(service_fn, **kwargs)
        return self._run_via_daemon(service_fn, **kwargs)

    def _run_local(self, service_fn: Callable, **kwargs) -> dict:
        """Local path: dispatch via in-process executor."""
        action = _get_action_name(service_fn)
        if action is None:
            raise RuntimeError(f"Service function {service_fn} not in DISPATCH table")

        try:
            result = self.executor.execute(action, kwargs, session=self.on)
        except MaafwError as e:
            self.fmt.error(str(e), exit_code=e.exit_code)
            return {}

        human_fn = getattr(service_fn, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)
        return result

    def _run_no_session(self, service_fn: Callable, **kwargs) -> dict:
        """Execute a service that doesn't require a session (via daemon IPC)."""
        from maafw_cli.core.ipc import DaemonClient, ensure_daemon

        action = _get_action_name(service_fn)
        if action is None:
            raise RuntimeError(f"Service function {service_fn} not in DISPATCH table")
        port = ensure_daemon()
        client = DaemonClient(port)
        try:
            result = client.send(action, kwargs, session=self.on)
        except MaafwError as e:
            self.fmt.error(str(e), exit_code=e.exit_code)
            return {}

        human_fn = getattr(service_fn, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)
        return result

    def run_raw(self, service_fn: Callable, **kwargs) -> dict:
        """Like :meth:`run` but returns the raw result without output formatting.

        Used by commands that need custom display logic (e.g. OCR text-only).
        Raises :class:`MaafwError` on failure.
        """
        action = _get_action_name(service_fn)
        if action is None:
            raise RuntimeError(f"Service function {service_fn} not in DISPATCH table")

        if self.executor is not None:
            return self.executor.execute(action, kwargs, session=self.on)

        from maafw_cli.core.ipc import DaemonClient, ensure_daemon
        port = ensure_daemon()
        client = DaemonClient(port)
        return client.send(action, kwargs, session=self.on)

    def _run_via_daemon(self, service_fn: Callable, **kwargs) -> dict:
        """Daemon path: send action + params over IPC."""
        from maafw_cli.core.ipc import DaemonClient, ensure_daemon

        action = _get_action_name(service_fn)
        if action is None:
            raise RuntimeError(f"Service function {service_fn} not in DISPATCH table")

        port = ensure_daemon()
        client = DaemonClient(port)

        try:
            result = client.send(action, kwargs, session=self.on)
        except MaafwError as e:
            self.fmt.error(str(e), exit_code=e.exit_code)
            return {}  # unreachable

        human_fn = getattr(service_fn, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)

        return result

pass_ctx = click.make_pass_decorator(CliContext, ensure=True)


# ── root group ──────────────────────────────────────────────────

@click.group(cls=GlobalOptionGroup)
@click.version_option(version=__version__, prog_name="maafw-cli")
@click.option("--json", "json_mode", is_flag=True, default=False, help="Output strict JSON to stdout.")
@click.option("--quiet", is_flag=True, default=False, help="Suppress non-error output.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show detailed timing and debug info.")
@click.option("--on", "on_session", default=None, envvar="MAAFW_SESSION", help="Target a named daemon session (env: MAAFW_SESSION).")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, quiet: bool, verbose: bool,
        on_session: str | None) -> None:
    """maafw-cli - MaaFramework command-line interface."""
    # Preserve executor if injected by REPL --local
    existing = ctx.obj if isinstance(ctx.obj, CliContext) else None
    executor = existing.executor if existing else None

    ctx.ensure_object(dict)
    setup_logging(verbose=verbose, quiet=quiet)
    ctx.obj = CliContext(
        json_mode=json_mode, quiet=quiet, verbose=verbose,
        on=on_session,
        executor=executor,
    )


# ── import sub-commands to register them ────────────────────────

from maafw_cli.commands.connection import device, connect  # noqa: E402
from maafw_cli.commands.vision import ocr, screenshot  # noqa: E402
from maafw_cli.commands.interaction import click_cmd, swipe_cmd, scroll_cmd, type_cmd, key_cmd  # noqa: E402
from maafw_cli.commands.recognition import reco_cmd  # noqa: E402
from maafw_cli.commands.resource import resource  # noqa: E402
from maafw_cli.commands.repl_cmd import repl_cmd  # noqa: E402
from maafw_cli.commands.daemon_cmd import daemon_group  # noqa: E402
from maafw_cli.commands.session_cmd import session_group  # noqa: E402
from maafw_cli.commands.pipeline import pipeline  # noqa: E402

cli.add_command(device)
cli.add_command(connect)
cli.add_command(ocr, name="ocr")
cli.add_command(screenshot, name="screenshot")
cli.add_command(reco_cmd, name="reco")
cli.add_command(click_cmd, name="click")
cli.add_command(swipe_cmd, name="swipe")
cli.add_command(scroll_cmd, name="scroll")
cli.add_command(type_cmd, name="type")
cli.add_command(key_cmd, name="key")
cli.add_command(resource)
cli.add_command(repl_cmd, name="repl")
cli.add_command(daemon_group, name="daemon")
cli.add_command(session_group, name="session")
cli.add_command(pipeline)
