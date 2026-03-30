"""
``maafw-cli repl`` — interactive REPL with persistent daemon session.

One connect, many operations, zero reconnection overhead.
Commands are forwarded to the Click CLI group, so every CLI command
(including future ones) is automatically available in the REPL.

With ``--local``, runs entirely in-process without daemon IPC.
"""
from __future__ import annotations

import shlex
import sys

import click

from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter


class Repl:
    """Interactive REPL that forwards input to the Click CLI group."""

    def __init__(
        self,
        fmt: OutputFormatter,
        on_session: str | None = None,
        executor: object | None = None,
    ):
        self.fmt = fmt
        self.on = on_session  # target session name
        self.executor = executor  # None = daemon, LocalExecutor = in-process

    # ── public API ──────────────────────────────────────────────

    def run(self) -> None:
        """Enter the readline loop.  Ctrl-D or ``quit`` to exit."""
        mode = "local" if self.executor else "daemon"
        print(f"maafw-cli REPL [{mode}] (type 'help' for commands, 'quit' to exit)")
        try:
            self._loop()
        finally:
            if self.executor is not None and hasattr(self.executor, "close_all"):
                self.executor.close_all()

    def _loop(self) -> None:
        while True:
            try:
                line = input("maafw> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in ("quit", "exit"):
                break
            if line == "status":
                self._print_status()
                continue
            self.execute_line(line)

    def execute_line(self, line: str) -> None:
        """Parse a line and forward it to the Click CLI group."""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return

        if not parts:
            return

        # Prevent recursive repl
        if parts[0] == "repl":
            print("Already in REPL mode.", file=sys.stderr)
            return

        # 'help' with no args → show root --help
        if parts == ["help"]:
            parts = ["--help"]

        argv = self._build_argv(parts)

        from maafw_cli.cli import cli, CliContext
        try:
            # Create Click context from argv (parses global options)
            ctx = cli.make_context("cli", argv)
            # Inject executor into ctx.obj so the cli callback preserves it
            if self.executor is not None:
                ctx.obj = CliContext(executor=self.executor)
            with ctx:
                cli.invoke(ctx)
        except SystemExit:
            pass  # fmt.error() calls sys.exit(); swallow it in REPL
        except click.exceptions.Exit:
            pass  # --help triggers click.Exit with code 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

    # ── argv construction ────────────────────────────────────────

    def _build_argv(self, parts: list[str]) -> list[str]:
        """Prepend global options to the command parts."""
        argv: list[str] = []
        if self.on:
            argv.extend(["--on", self.on])
        if self.fmt.json_mode:
            argv.append("--json")
        if self.fmt.quiet:
            argv.append("--quiet")
        argv.extend(parts)
        return argv

    # ── status (REPL-only built-in) ──────────────────────────────

    def _print_status(self) -> None:
        """Show session status (local or daemon)."""
        try:
            if self.executor is not None:
                result = self.executor.execute("session_list", {})
            else:
                from maafw_cli.core.ipc import DaemonClient, ensure_daemon
                port = ensure_daemon()
                client = DaemonClient(port)
                result = client.send("session_list", {}, session=self.on)

            sessions = result.get("sessions", [])
            if not sessions:
                print("No active sessions.")
            else:
                for s in sessions:
                    default = " (default)" if s.get("is_default") else ""
                    connected = "connected" if s.get("connected") else "disconnected"
                    print(f"  {s['name']}{default}: {s.get('type', '?')} | {s.get('device', '?')} | {connected}")
            mode = "local" if self.executor else "daemon"
            print(f"Target session: {self.on or '(default)'}  [{mode}]")
        except MaafwError as e:
            print(f"Error: {e}", file=sys.stderr)


@click.command("repl")
@click.option("--local", is_flag=True, default=False,
              help="Run in-process without daemon (single device, zero IPC overhead).")
@click.pass_context
def repl_cmd(ctx: click.Context, local: bool) -> None:
    """Start an interactive REPL with persistent controller."""
    cli_ctx = ctx.find_root().obj
    executor = None
    if local:
        from maafw_cli.core.local_executor import LocalExecutor
        executor = LocalExecutor()

    repl = Repl(cli_ctx.fmt, on_session=cli_ctx.on, executor=executor)
    repl.run()
