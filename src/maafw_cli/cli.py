"""
Root CLI group and global options (--json, --quiet, --on, --no-daemon).

All sub-commands are registered here.
"""
from __future__ import annotations

import logging
from typing import Callable

import click

from maafw_cli import __version__
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.log import setup_logging
from maafw_cli.core.output import OutputFormatter

_log = logging.getLogger("maafw_cli.cli")


# ── action name reverse-lookup ─────────────────────────────────

def _get_action_name(fn: Callable) -> str | None:
    """Return the DISPATCH key for a service function."""
    return getattr(fn, "dispatch_key", None)


# ── shared context ──────────────────────────────────────────────

class CliContext:
    """Carries global state through Click's context."""

    def __init__(
        self,
        *,
        json_mode: bool = False,
        quiet: bool = False,
        verbose: bool = False,
        observe: bool = False,
        on: str | None = None,
        no_daemon: bool = False,
    ):
        self.fmt = OutputFormatter(json_mode=json_mode, quiet=quiet)
        self.verbose = verbose
        self.observe = observe
        self.on = on          # --on <session>: target specific daemon session
        self.no_daemon = no_daemon  # --no-daemon: skip daemon, use direct mode

    def _make_service_context(self):
        """Build a :class:`ServiceContext` for the current session (direct mode)."""
        from maafw_cli.core.reconnect import reconnect
        from maafw_cli.core.session import load_session, textrefs_file
        from maafw_cli.services.context import ServiceContext

        session = load_session()
        session_type = session.type if session else "win32"

        return ServiceContext(
            get_controller=lambda: reconnect(),
            textrefs_path=textrefs_file(),
            session_type=session_type,
        )

    def run(self, service_fn: Callable, **kwargs) -> dict:
        """Call a service function — routes via daemon or direct.

        Routing logic:
        - ``--no-daemon`` → direct (Phase 1 path, reconnect from session.json)
        - Default → daemon (IPC to background process)

        Automatically handles ``needs_session`` — services that don't need
        a session (e.g. ``device_list``) are called directly without a
        ServiceContext.
        """
        needs_session = getattr(service_fn, "needs_session", True)

        if not needs_session:
            return self._run_no_session(service_fn, **kwargs)
        if self.no_daemon:
            return self._run_direct(service_fn, **kwargs)
        return self._run_via_daemon(service_fn, **kwargs)

    def _run_no_session(self, service_fn: Callable, **kwargs) -> dict:
        """Execute a service that doesn't require a session.

        In daemon mode, still routes via IPC so the daemon can handle it.
        In direct mode, calls the function directly.
        """
        if self.no_daemon:
            try:
                result = service_fn(**kwargs)
            except MaafwError as e:
                self.fmt.error(str(e), exit_code=e.exit_code)
                return {}
        else:
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

    def _run_direct(self, service_fn: Callable, **kwargs) -> dict:
        """Phase 1 path: reconnect from session.json every time."""
        svc_ctx = self._make_service_context()
        try:
            result = service_fn(svc_ctx, **kwargs)
        except MaafwError as e:
            self.fmt.error(str(e), exit_code=e.exit_code)
            return {}  # unreachable — fmt.error exits

        human_fn = getattr(service_fn, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)

        # --observe: auto-OCR after action commands
        if self.observe and result.get("action"):
            self._run_observe(svc_ctx, result)

        return result

    def run_raw(self, service_fn: Callable, **kwargs) -> dict:
        """Like :meth:`run` but returns the raw result without output formatting.

        Used by commands that need custom display logic (e.g. OCR text-only).
        Raises :class:`MaafwError` on failure.
        """
        needs_session = getattr(service_fn, "needs_session", True)

        if not needs_session:
            if self.no_daemon:
                return service_fn(**kwargs)
            return self._run_raw_daemon(service_fn, **kwargs)
        if self.no_daemon:
            return self._run_raw_direct(service_fn, **kwargs)
        return self._run_raw_daemon(service_fn, **kwargs)

    def _run_raw_direct(self, service_fn: Callable, **kwargs) -> dict:
        svc_ctx = self._make_service_context()
        return service_fn(svc_ctx, **kwargs)

    def _run_raw_daemon(self, service_fn: Callable, **kwargs) -> dict:
        from maafw_cli.core.ipc import DaemonClient, ensure_daemon
        action = _get_action_name(service_fn)
        if action is None:
            raise RuntimeError(f"Service function {service_fn} not in DISPATCH table")
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

        # --observe: auto-OCR after action commands (via daemon)
        if self.observe and result.get("action"):
            self._run_observe_daemon(client)

        return result

    def _run_observe(self, svc_ctx, action_result: dict) -> None:
        """Run OCR after an action and output the results (direct mode)."""
        from maafw_cli.services.vision import do_ocr

        try:
            ocr_result = do_ocr(svc_ctx)
        except MaafwError:
            return  # observe is best-effort

        self._display_observe(ocr_result)

    def _run_observe_daemon(self, client) -> None:
        """Run OCR after an action via daemon IPC (daemon mode)."""
        try:
            ocr_result = client.send("ocr", {}, session=self.on)
        except MaafwError:
            return  # observe is best-effort

        self._display_observe(ocr_result)

    def _display_observe(self, ocr_result: dict) -> None:
        """Display observe OCR results."""
        refs = ocr_result["results"]
        elapsed_ms = ocr_result["elapsed_ms"]

        if self.fmt.json_mode:
            self.fmt.success(ocr_result)
        elif refs:
            human = OutputFormatter.format_ocr_table(refs, elapsed_ms)
            self.fmt.success(ocr_result, human=human)


pass_ctx = click.make_pass_decorator(CliContext, ensure=True)


# ── root group ──────────────────────────────────────────────────

@click.group()
@click.version_option(version=__version__, prog_name="maafw-cli")
@click.option("--json", "json_mode", is_flag=True, default=False, help="Output strict JSON to stdout.")
@click.option("--quiet", is_flag=True, default=False, help="Suppress non-error output.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show detailed timing and debug info.")
@click.option("--observe", is_flag=True, default=False, help="Auto-OCR after action commands.")
@click.option("--on", "on_session", default=None, help="Target a named daemon session.")
@click.option("--no-daemon", is_flag=True, default=False, help="Skip daemon, use direct reconnect mode.")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, quiet: bool, verbose: bool,
        observe: bool, on_session: str | None, no_daemon: bool) -> None:
    """maafw-cli — MaaFramework command-line interface."""
    ctx.ensure_object(dict)
    setup_logging(verbose=verbose, quiet=quiet)
    ctx.obj = CliContext(
        json_mode=json_mode, quiet=quiet, verbose=verbose,
        observe=observe, on=on_session, no_daemon=no_daemon,
    )


# ── exit codes (kept for backward compat imports) ────────────────
EXIT_SUCCESS = 0
EXIT_ACTION_FAILED = 1
EXIT_RECOGNITION_FAILED = 2
EXIT_CONNECTION_ERROR = 3


# ── import sub-commands to register them ────────────────────────

from maafw_cli.commands.connection import device, connect  # noqa: E402
from maafw_cli.commands.vision import ocr, screenshot  # noqa: E402
from maafw_cli.commands.interaction import click_cmd, swipe_cmd, scroll_cmd, type_cmd, key_cmd  # noqa: E402
from maafw_cli.commands.resource import resource  # noqa: E402
from maafw_cli.commands.repl_cmd import repl_cmd  # noqa: E402
from maafw_cli.commands.daemon_cmd import daemon_group  # noqa: E402
from maafw_cli.commands.session_cmd import session_group  # noqa: E402

cli.add_command(device)
cli.add_command(connect)
cli.add_command(ocr, name="ocr")
cli.add_command(screenshot, name="screenshot")
cli.add_command(click_cmd, name="click")
cli.add_command(swipe_cmd, name="swipe")
cli.add_command(scroll_cmd, name="scroll")
cli.add_command(type_cmd, name="type")
cli.add_command(key_cmd, name="key")
cli.add_command(resource)
cli.add_command(repl_cmd, name="repl")
cli.add_command(daemon_group, name="daemon")
cli.add_command(session_group, name="session")
