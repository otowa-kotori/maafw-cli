"""
``maafw-cli repl`` — interactive REPL with a persistent controller.

One connect, many operations, zero reconnection overhead.
"""
from __future__ import annotations

import shlex
import sys

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import DISPATCH

# Ensure all services are registered in DISPATCH
import maafw_cli.services.interaction  # noqa: F401
import maafw_cli.services.vision  # noqa: F401
import maafw_cli.services.connection  # noqa: F401


class Repl:
    """Interactive REPL that keeps the controller alive across commands."""

    def __init__(self, fmt: OutputFormatter):
        self.fmt = fmt
        self._svc_ctx: ServiceContext | None = None
        self.observe: bool = False

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
        if cmd == "observe":
            self._toggle_observe(args)
            return None

        # Connection commands (special — they don't use ServiceContext)
        if cmd == "connect":
            return self._handle_connect(args)

        # Regular service dispatch
        handler = DISPATCH.get(cmd)
        if handler is None:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.", file=sys.stderr)
            return None

        if self._svc_ctx is None:
            self._ensure_service_context()
            if self._svc_ctx is None:
                return None

        kwargs = self._parse_service_args(cmd, args)
        if kwargs is None:
            return None

        try:
            result = handler(self._svc_ctx, **kwargs)
        except MaafwError as e:
            print(f"Error: {e}", file=sys.stderr)
            return None

        # Output
        human_fn = getattr(handler, "human_fmt", None)
        human = human_fn(result) if human_fn else None
        self.fmt.success(result, human=human)

        # observe: auto-OCR after action commands
        if self.observe and result.get("action"):
            self._run_observe()

        return result

    # ── connection handling ─────────────────────────────────────

    def _handle_connect(self, args: list[str]) -> dict | None:
        if len(args) < 2:
            print("Usage: connect adb <device> | connect win32 <window>", file=sys.stderr)
            return None

        subtype = args[0]
        target = args[1]

        try:
            if subtype == "adb":
                from maafw_cli.services.connection import do_connect_adb
                result = do_connect_adb(target)
            elif subtype == "win32":
                from maafw_cli.services.connection import do_connect_win32
                # Parse optional --input-method / --screencap-method
                kw: dict = {}
                i = 2
                while i < len(args):
                    if args[i] == "--input-method" and i + 1 < len(args):
                        kw["input_method"] = args[i + 1]
                        i += 2
                    elif args[i] == "--screencap-method" and i + 1 < len(args):
                        kw["screencap_method"] = args[i + 1]
                        i += 2
                    else:
                        i += 1
                result = do_connect_win32(target, **kw)
            else:
                print(f"Unknown connect type: {subtype}", file=sys.stderr)
                return None
        except MaafwError as e:
            print(f"Error: {e}", file=sys.stderr)
            return None

        # Invalidate cached controller and rebuild service context
        self._rebuild_service_context()
        self.fmt.success(result, human=f"Connected to {target}")
        return result

    # ── service context management ─────────────────────────────

    def _ensure_service_context(self) -> None:
        """Try to build a ServiceContext from the existing session."""
        from maafw_cli.core.session import load_session, textrefs_file
        session = load_session()
        if session is None:
            print("No active session. Run 'connect adb <device>' or 'connect win32 <window>' first.",
                  file=sys.stderr)
            return

        from maafw_cli.core.reconnect import reconnect

        # Build a ServiceContext that connects lazily
        self._svc_ctx = ServiceContext(
            get_controller=lambda: reconnect(),
            textrefs_path=textrefs_file(),
            session_type=session.type,
        )

    def _rebuild_service_context(self) -> None:
        """Rebuild after a connect command — invalidate cached controller."""
        if self._svc_ctx is not None:
            self._svc_ctx.invalidate_controller()
        self._svc_ctx = None  # force fresh build on next command
        self._ensure_service_context()

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
                kw["duration"] = int(args[i + 1])
                i += 2
            else:
                i += 1
        return kw

    @staticmethod
    def _parse_scroll(args: list[str]) -> dict | None:
        if len(args) != 2:
            print("Usage: scroll <dx> <dy>", file=sys.stderr)
            return None
        return {"dx": int(args[0]), "dy": int(args[1])}

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
            "observe on|off               Toggle auto-OCR after actions",
            "status                       Show session info",
            "help                         Show this help",
            "quit                         Exit REPL",
        ]
        print("\n".join(cmds))

    def _print_status(self) -> None:
        from maafw_cli.core.session import load_session
        session = load_session()
        if session is None:
            print("No active session.")
        else:
            print(f"Session: {session.type} | {session.device} | {session.address}")
            has_ctrl = self._svc_ctx is not None and "controller" in self._svc_ctx.__dict__
            print(f"Controller cached: {has_ctrl}")
            print(f"Observe: {'on' if self.observe else 'off'}")

    def _toggle_observe(self, args: list[str]) -> None:
        if not args or args[0] not in ("on", "off"):
            print("Usage: observe on|off", file=sys.stderr)
            return
        self.observe = args[0] == "on"
        print(f"Observe: {'on' if self.observe else 'off'}")

    def _run_observe(self) -> None:
        """Run OCR after an action (best-effort)."""
        from maafw_cli.services.vision import do_ocr
        from maafw_cli.core.output import OutputFormatter

        try:
            ocr_result = do_ocr(self._svc_ctx)
        except MaafwError:
            return

        refs = ocr_result["results"]
        elapsed_ms = ocr_result["elapsed_ms"]
        if not refs:
            return

        if self.fmt.json_mode:
            self.fmt.success(ocr_result)
        else:
            human = OutputFormatter.format_ocr_table(refs, elapsed_ms)
            self.fmt.success(ocr_result, human=human)


@click.command("repl")
@pass_ctx
def repl_cmd(ctx: CliContext) -> None:
    """Start an interactive REPL with persistent controller."""
    repl = Repl(ctx.fmt)
    repl.run()
