"""
REPL dispatch tests — verify command parsing and service routing.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from maafw_cli.core.output import OutputFormatter
from maafw_cli.commands.repl_cmd import Repl
from maafw_cli.services.context import ServiceContext
from mock_controller import MockController


def _make_repl(mock: MockController | None = None, json_mode: bool = False) -> Repl:
    """Build a Repl with a pre-wired ServiceContext backed by MockController."""
    if mock is None:
        mock = MockController()
    fmt = OutputFormatter(json_mode=json_mode, quiet=True)
    repl = Repl(fmt)
    repl._svc_ctx = ServiceContext(
        get_controller=lambda: mock,
        elements_path=Path("/nonexistent"),
        session_type="win32",
    )
    return repl


class TestReplDispatch:
    def test_click(self):
        mock = MockController()
        repl = _make_repl(mock)
        result = repl.execute_line("click 100,200")
        assert result is not None
        assert result["action"] == "click"
        assert mock.clicks == [(100, 200)]

    def test_swipe(self):
        mock = MockController()
        repl = _make_repl(mock)
        result = repl.execute_line("swipe 100,800 100,200 --duration 500")
        assert result is not None
        assert result["x1"] == 100
        assert result["y2"] == 200
        assert result["duration"] == 500

    def test_scroll(self):
        mock = MockController()
        repl = _make_repl(mock)
        result = repl.execute_line("scroll 0 -360")
        assert result is not None
        assert result["dx"] == 0
        assert result["dy"] == -360

    def test_type(self):
        mock = MockController()
        repl = _make_repl(mock)
        result = repl.execute_line('type "Hello World"')
        assert result is not None
        assert result["text"] == "Hello World"

    def test_key(self):
        mock = MockController()
        repl = _make_repl(mock)
        result = repl.execute_line("key enter")
        assert result is not None
        assert result["keycode"] == 0x0D  # win32 default

    def test_unknown_command(self, capsys):
        repl = _make_repl()
        result = repl.execute_line("nonexistent_cmd")
        assert result is None

    def test_error_does_not_exit(self):
        """Errors in REPL should print, not sys.exit."""
        mock = MockController(click_ok=False)
        repl = _make_repl(mock)
        # Should not raise SystemExit
        result = repl.execute_line("click 100,200")
        assert result is None

    def test_help(self, capsys):
        repl = _make_repl()
        result = repl.execute_line("help")
        captured = capsys.readouterr()
        assert "click" in captured.out
        assert "swipe" in captured.out

    def test_status_no_session(self, capsys):
        repl = _make_repl()
        repl._svc_ctx = None
        with patch("maafw_cli.core.session.load_session", return_value=None):
            repl.execute_line("status")
        captured = capsys.readouterr()
        assert "No active session" in captured.out

    def test_observe_toggle(self, capsys):
        repl = _make_repl()
        assert repl.observe is False
        repl.execute_line("observe on")
        assert repl.observe is True
        repl.execute_line("observe off")
        assert repl.observe is False

    def test_observe_bad_arg(self, capsys):
        repl = _make_repl()
        repl.execute_line("observe maybe")
        assert repl.observe is False  # unchanged


class TestReplParseErrors:
    """REPL should handle invalid arguments gracefully, not crash."""

    def test_swipe_bad_duration(self, capsys):
        repl = _make_repl()
        result = repl.execute_line("swipe 0,0 100,100 --duration abc")
        assert result is None
        captured = capsys.readouterr()
        assert "integer" in captured.err.lower()

    def test_scroll_bad_args(self, capsys):
        repl = _make_repl()
        result = repl.execute_line("scroll abc def")
        assert result is None
        captured = capsys.readouterr()
        assert "integer" in captured.err.lower()


class TestReplJsonMode:
    """REPL should output JSON when formatter is in json_mode."""

    def test_click_json_output(self, capsys):
        mock = MockController()
        repl = _make_repl(mock, json_mode=True)
        result = repl.execute_line("click 100,200")
        assert result is not None
        assert result["action"] == "click"
        # In json_mode with quiet=True the output goes through fmt
        # Just verify the command succeeded
        assert mock.clicks == [(100, 200)]
