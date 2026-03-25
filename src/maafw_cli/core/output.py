"""
Output formatting module — human / json / quiet modes.

Every command uses this module to produce consistent output.
- Human mode: formatted, aligned text to stdout
- JSON mode: strict JSON to stdout
- Quiet mode: suppress everything except errors
"""
from __future__ import annotations

import json
import sys
from typing import Any, NoReturn


class OutputFormatter:
    """Formats command output based on the selected mode."""

    def __init__(self, *, json_mode: bool = False, quiet: bool = False):
        self.json_mode = json_mode
        self.quiet = quiet

    # ── public API ──────────────────────────────────────────────

    def success(self, data: dict[str, Any] | list[Any], human: str | None = None) -> None:
        """Print a successful result.

        *data* is the machine-readable payload (used in ``--json`` mode).
        *human* is the pretty string shown in default mode.  When *human*
        is ``None`` the data dict is printed as indented JSON even in
        human mode (fallback).
        """
        if self.quiet:
            return
        if self.json_mode:
            self._print_json(data)
        else:
            if human is not None:
                self._print_text(human)
            else:
                self._print_json(data)

    def print_error(self, message: str) -> None:
        """Format and print an error message (without exiting).

        Use this when the caller handles the exit/flow control itself.
        """
        if self.json_mode:
            self._print_json({"error": message})
        elif not self.quiet:
            self._print_text(f"Error: {message}", file=sys.stderr)

    def error(self, message: str, *, exit_code: int = 1) -> NoReturn:
        """Print an error to stderr and exit.

        Convenience method that combines :meth:`print_error` with ``sys.exit``.
        """
        self.print_error(message)
        sys.exit(exit_code)

    def info(self, message: str) -> None:
        """Print informational / progress text to stderr (never captured by pipes).

        Delegates to the unified ``maafw_cli`` logger so that ``--verbose``
        and ``--quiet`` are handled in one place.
        """
        from maafw_cli.core.log import logger

        logger.info(message)

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    def _print_text(text: str, file: Any = None) -> None:
        """Print text safely on Windows (UTF-8 via buffer when available)."""
        target = file or sys.stdout
        if hasattr(target, "buffer"):
            target.buffer.write(text.encode("utf-8"))
            target.buffer.write(b"\n")
            target.buffer.flush()
        else:
            target.write(text)
            target.write("\n")
            target.flush()

    def _print_json(self, obj: Any) -> None:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
        target = sys.stdout
        if hasattr(target, "buffer"):
            target.buffer.write(text.encode("utf-8"))
            target.buffer.write(b"\n")
            target.buffer.flush()
        else:
            target.write(text)
            target.write("\n")
            target.flush()

    # ── OCR formatting ───────────────────────────────────────────

    @staticmethod
    def format_ocr_table(refs: list[dict], elapsed_ms: int, session_label: str = "default") -> str:
        """Format OCR results as a human-readable table.

        Used by ``ocr`` command and ``--observe`` mode.
        """
        lines: list[str] = []
        lines.append(f"Screen OCR \u2014 {session_label}")
        lines.append("\u2500" * 60)
        for r in refs:
            box = r["box"]
            box_str = f"[{box[0]:>4},{box[1]:>4},{box[2]:>4},{box[3]:>4}]"
            score_str = f"{r['score'] * 100:.0f}%"
            lines.append(f" {r['ref']:<4s} {r['text']:<20s} {box_str}  {score_str}")
        lines.append("\u2500" * 60)
        lines.append(f"{len(refs)} results | {elapsed_ms}ms")
        return "\n".join(lines)
