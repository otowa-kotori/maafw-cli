"""
``maafw-cli repl`` — interactive REPL with persistent daemon session.

One connect, many operations, zero reconnection overhead.
"""
from __future__ import annotations

import shlex
import sys

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter
from maafw_cli.services.registry import DISPATCH

# Ensure all services are registered in DISPATCH
import maafw_cli.services.interaction  # noqa: F401
import maafw_cli.services.vision  # noqa: F401
import maafw_cli.services.connection  # noqa: F401


class Repl:
    """Interactive REPL that routes commands through the daemon."""

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
            self.execute_line(line)

    def execute_line(self, line: str) -> dict | None:
        """Parse and dispatch a single line.  Returns result dict or None."""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return None

        cmd = parts[0]
        args = parts[1:]

        # Built-in commands
        if cmd == "help":
            self._print_help()
            return None
        if cmd == "status":
            self._print_status()
            return None

        # Connection commands (special — routed through daemon)
        if cmd == "connect":
            return self._handle_connect(args)

        # Regular service dispatch via daemon
        handler = DISPATCH.get(cmd)
        if handler is None:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.", file=sys.stderr)
            return None

        kwargs = self._parse_service_args(cmd, args)
        if kwargs is None:
            return None

        try:
            result = self._send(cmd, kwargs)
        except MaafwError as e:
            print(f"Error: {e}", file=sys.stderr)
            return None

        # Output
        human_fn = getattr(handler, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)

        return result

    # ── daemon IPC ─────────────────────────────────────────────

    def _send(self, action: str, params: dict) -> dict:
        """Send a command to the daemon."""
        from maafw_cli.core.ipc import DaemonClient, ensure_daemon

        port = ensure_daemon()
        client = DaemonClient(port)
        return client.send(action, params, session=self.on)

    # ── connection handling ─────────────────────────────────────

    def _handle_connect(self, args: list[str]) -> dict | None:
        if len(args) < 2:
            print("Usage: connect adb <device> | connect win32 <window>", file=sys.stderr)
            return None

        subtype = args[0]
        target = args[1]

        try:
            if subtype == "adb":
                result = self._send("connect_adb", {"device": target})
            elif subtype == "win32":
                # Parse optional --input-method / --screencap-method
                kw: dict = {"window": target}
                i = 2
                while i < len(args):
                    if args[i] == "--input-method" and i + 1 < len(args):
                        kw["input_method"] = args[i + 1]
                        i += 2
                    elif args[i] == "--screencap-method" and i + 1 < len(args):
                        kw["screencap_method"] = args[i + 1]
                        i += 2
                    else:
                        print(f"Warning: unknown argument '{args[i]}'", file=sys.stderr)
                        i += 1
                result = self._send("connect_win32", kw)
            else:
                print(f"Unknown connect type: {subtype}", file=sys.stderr)
                return None
        except MaafwError as e:
            print(f"Error: {e}", file=sys.stderr)
            return None

        # Update target session if the connect returned one
        if "session" in result:
            self.on = result["session"]

        self.fmt.success(result, human=f"Connected to {target}")
        return result

    # ── argument parsing ───────────────────────────────────────

    def _parse_service_args(self, cmd: str, args: list[str]) -> dict | None:
        """Simple positional/flag argument parsing for REPL commands."""
        # Map command names to expected argument patterns
        parsers = {
            "click": self._parse_click,
            "swipe": self._parse_swipe,
            "scroll": self._parse_scroll,
            "type": self._parse_type,
            "key": self._parse_key,
            "ocr": self._parse_ocr,
            "screenshot": self._parse_screenshot,
        }
        parser = parsers.get(cmd)
        if parser is None:
            # Generic: pass args as positional
            return {}
        return parser(args)

    @staticmethod
    def _parse_click(args: list[str]) -> dict | None:
        if len(args) != 1:
            print("Usage: click <target>", file=sys.stderr)
            return None
        return {"target": args[0]}

    @staticmethod
    def _parse_swipe(args: list[str]) -> dict | None:
        if len(args) < 2:
            print("Usage: swipe <from> <to> [--duration N]", file=sys.stderr)
            return None
        kw: dict = {"from_target": args[0], "to_target": args[1]}
        i = 2
        while i < len(args):
            if args[i] == "--duration" and i + 1 < len(args):
                try:
                    kw["duration"] = int(args[i + 1])
                except ValueError:
                    print(f"Error: duration must be an integer, got '{args[i + 1]}'", file=sys.stderr)
                    return None
                i += 2
            else:
                print(f"Warning: unknown argument '{args[i]}'", file=sys.stderr)
                i += 1
        return kw

    @staticmethod
    def _parse_scroll(args: list[str]) -> dict | None:
        if len(args) != 2:
            print("Usage: scroll <dx> <dy>", file=sys.stderr)
            return None
        try:
            return {"dx": int(args[0]), "dy": int(args[1])}
        except ValueError:
            print(f"Error: scroll dx/dy must be integers, got '{args[0]}', '{args[1]}'", file=sys.stderr)
            return None

    @staticmethod
    def _parse_type(args: list[str]) -> dict | None:
        if len(args) != 1:
            print("Usage: type <text>", file=sys.stderr)
            return None
        return {"text": args[0]}

    @staticmethod
    def _parse_key(args: list[str]) -> dict | None:
        if len(args) != 1:
            print("Usage: key <keycode>", file=sys.stderr)
            return None
        return {"keycode": args[0]}

    @staticmethod
    def _parse_ocr(args: list[str]) -> dict | None:
        kw: dict = {}
        i = 0
        while i < len(args):
            if args[i] == "--roi" and i + 1 < len(args):
                kw["roi"] = args[i + 1]
                i += 2
            else:
                i += 1
        return kw

    @staticmethod
    def _parse_screenshot(args: list[str]) -> dict | None:
        kw: dict = {}
        if len(args) >= 2 and args[0] in ("-o", "--output"):
            kw["output"] = args[1]
        elif len(args) == 1:
            kw["output"] = args[0]
        return kw

    # ── help / status ──────────────────────────────────────────

    def _print_help(self) -> None:
        cmds = [
            "connect adb <device>         Connect to ADB device",
            "connect win32 <window>       Connect to Win32 window",
            "ocr [--roi x,y,w,h]         Run OCR",
            "screenshot [-o FILE]         Take screenshot",
            "click <target>               Click (t3 or 452,387)",
            "swipe <from> <to>            Swipe between targets",
            "scroll <dx> <dy>             Scroll",
            "type <text>                  Input text",
            "key <keycode>                Press key",
            "status                       Show session info",
            "help                         Show this help",
            "quit                         Exit REPL",
        ]
        print("\n".join(cmds))

    def _print_status(self) -> None:
        try:
            result = self._send("session_list", {})
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
