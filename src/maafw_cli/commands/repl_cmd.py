"""
``maafw-cli repl`` — interactive REPL with persistent daemon session.

One connect, many operations, zero reconnection overhead.
Commands are forwarded to the Click CLI group, so every CLI command
(including future ones) is automatically available in the REPL.
"""
from __future__ import annotations

import shlex
import sys

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter


class Repl:
    """Interactive REPL that forwards input to the Click CLI group."""

    def __init__(self, fmt: OutputFormatter, on_session: str | None = None):
        self.fmt = fmt
        self.on = on_session  # target session name

    # ── public API ──────────────────────────────────────────────

    def run(self) -> None:
        """Enter the readline loop.  Ctrl-D or ``quit`` to exit."""
        print("maafw-cli REPL (type 'help' for commands, 'quit' to exit)")
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

        from maafw_cli.cli import cli
        try:
            cli(argv, standalone_mode=False)
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
        """Show daemon session status."""
        from maafw_cli.core.ipc import DaemonClient, ensure_daemon

        try:
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
            print(f"Target session: {self.on or '(default)'}")
        except MaafwError as e:
            print(f"Error: {e}", file=sys.stderr)


@click.command("repl")
@pass_ctx
def repl_cmd(ctx: CliContext) -> None:
    """Start an interactive REPL with persistent controller."""
    repl = Repl(ctx.fmt, on_session=ctx.on)
    repl.run()
