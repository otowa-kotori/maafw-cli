"""
REPL dispatch tests — verify command parsing and daemon routing.
"""
from __future__ import annotations

from unittest.mock import patch

from maafw_cli.core.output import OutputFormatter
from maafw_cli.commands.repl_cmd import Repl


def _make_repl(json_mode: bool = False, on_session: str = "test") -> Repl:
    """Build a Repl for testing."""
    fmt = OutputFormatter(json_mode=json_mode, quiet=True)
    return Repl(fmt, on_session=on_session)


def _mock_send(action, params, session=None):
    """Default mock for daemon IPC that handles common commands."""
    if action == "click":
        target = params.get("target", "0,0")
        if "," in target:
            x, y = target.split(",")
            return {"action": "click", "x": int(x), "y": int(y), "source": "coord"}
        return {"action": "click", "x": 0, "y": 0, "source": "element"}
    if action == "swipe":
        return {
            "action": "swipe",
            "x1": 100, "y1": 800, "x2": 100, "y2": 200,
            "duration": params.get("duration", 300),
            "from_source": "coord", "to_source": "coord",
        }
    if action == "scroll":
        return {"action": "scroll", "dx": params.get("dx", 0), "dy": params.get("dy", 0)}
    if action == "type":
        return {"action": "type", "text": params.get("text", "")}
    if action == "key":
        return {"action": "key", "keycode": 0x0D, "keycode_hex": "0x0D",
                "name": params.get("keycode", ""), "session_type": "win32"}
    return {}


class TestReplDispatch:
    def test_click(self):
        repl = _make_repl()
        with patch.object(repl, "_send", side_effect=_mock_send):
            result = repl.execute_line("click 100,200")
        assert result is not None
        assert result["action"] == "click"

    def test_swipe(self):
        repl = _make_repl()
        with patch.object(repl, "_send", side_effect=_mock_send):
            result = repl.execute_line("swipe 100,800 100,200 --duration 500")
        assert result is not None
        assert result["action"] == "swipe"

    def test_scroll(self):
        repl = _make_repl()
        with patch.object(repl, "_send", side_effect=_mock_send):
            result = repl.execute_line("scroll 0 -360")
        assert result is not None
        assert result["action"] == "scroll"

    def test_type(self):
        repl = _make_repl()
        with patch.object(repl, "_send", side_effect=_mock_send):
            result = repl.execute_line('type "Hello World"')
        assert result is not None
        assert result["action"] == "type"

    def test_key(self):
        repl = _make_repl()
        with patch.object(repl, "_send", side_effect=_mock_send):
            result = repl.execute_line("key enter")
        assert result is not None
        assert result["action"] == "key"

    def test_unknown_command(self, capsys):
        repl = _make_repl()
        result = repl.execute_line("nonexistent_cmd")
        assert result is None

    def test_error_does_not_exit(self):
        """Errors in REPL should print, not sys.exit."""
        from maafw_cli.core.errors import ActionError
        repl = _make_repl()
        with patch.object(repl, "_send", side_effect=ActionError("Click failed.")):
            result = repl.execute_line("click 100,200")
        assert result is None

    def test_help(self, capsys):
        repl = _make_repl()
        repl.execute_line("help")
        captured = capsys.readouterr()
        assert "click" in captured.out
        assert "swipe" in captured.out

    def test_status_via_daemon(self, capsys):
        repl = _make_repl()
        mock_result = {"sessions": []}
        with patch.object(repl, "_send", return_value=mock_result):
            repl.execute_line("status")
        captured = capsys.readouterr()
        assert "No active sessions" in captured.out

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
        repl = _make_repl(json_mode=True)
        with patch.object(repl, "_send", side_effect=_mock_send):
            result = repl.execute_line("click 100,200")
        assert result is not None
        assert result["action"] == "click"
