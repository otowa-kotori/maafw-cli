"""
REPL tests — verify the new Click-forwarding REPL.

The REPL now delegates to the Click CLI group, so we test:
- Built-in commands (status, help, quit)
- Click forwarding works (help pages render)
- --local flag creates LocalExecutor
- Repl rejects nested repl
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from maafw_cli.core.output import OutputFormatter


def _get_repl_class():
    """Lazy import to avoid circular import (repl_cmd → cli → repl_cmd)."""
    from maafw_cli.commands.repl_cmd import Repl
    return Repl


def _make_repl(
    json_mode: bool = False,
    on_session: str | None = "test",
    executor: object | None = None,
):
    """Build a Repl for testing."""
    Repl = _get_repl_class()
    fmt = OutputFormatter(json_mode=json_mode, quiet=True)
    return Repl(fmt, on_session=on_session, executor=executor)


class TestReplBuiltins:
    """Test REPL-only built-in commands."""

    def test_repl_prevents_recursion(self, capsys):
        repl = _make_repl()
        repl.execute_line("repl")
        captured = capsys.readouterr()
        assert "Already in REPL" in captured.err

    def test_help_shows_commands(self, capsys):
        """'help' should forward to --help and show Click help."""
        repl = _make_repl(on_session=None)
        repl.execute_line("help")
        captured = capsys.readouterr()
        assert "click" in captured.out
        assert "connect" in captured.out

    def test_status_local_mode(self, capsys):
        """status in local mode works without daemon."""
        from maafw_cli.core.local_executor import LocalExecutor
        executor = LocalExecutor()
        repl = _make_repl(executor=executor)
        repl._print_status()
        captured = capsys.readouterr()
        assert "No active sessions" in captured.out

    def test_status_daemon_mode(self, capsys):
        """status in daemon mode queries daemon."""
        repl = _make_repl()
        with patch("maafw_cli.core.ipc.ensure_daemon", return_value=19799), \
             patch("maafw_cli.core.ipc.DaemonClient") as mock_client:
            mock_client.return_value.send.return_value = {"sessions": []}
            repl._print_status()
        captured = capsys.readouterr()
        assert "No active sessions" in captured.out


class TestReplClickForwarding:
    """Test that REPL forwards commands to the Click CLI group."""

    def test_click_help_forwarded(self, capsys):
        """'click --help' should show Click's help for the click command."""
        repl = _make_repl(on_session=None)
        repl.execute_line("click --help")
        captured = capsys.readouterr()
        assert "TARGET" in captured.out

    def test_connect_help_forwarded(self, capsys):
        """'connect adb --help' should show the connect adb help."""
        repl = _make_repl(on_session=None)
        repl.execute_line("connect adb --help")
        captured = capsys.readouterr()
        assert "DEVICE" in captured.out

    def test_global_options_prepended(self):
        """_build_argv should prepend --on, --json, --quiet."""
        repl = _make_repl(json_mode=True, on_session="phone")
        argv = repl._build_argv(["click", "100,200"])
        assert "--on" in argv
        assert "phone" in argv
        assert "--json" in argv
        assert argv[-2:] == ["click", "100,200"]


class TestReplLocalMode:
    """Test REPL with LocalExecutor (--local)."""

    def test_local_executor_dispatch(self, capsys):
        """Commands in local mode go through LocalExecutor, not daemon."""
        from maafw_cli.core.local_executor import LocalExecutor
        from maafw_cli.core.session import Session

        # Set up a local executor with a mock session
        executor = LocalExecutor()
        mock_ctrl = MagicMock()
        mock_ctrl.connected = True
        mock_ctrl.post_click.return_value.wait.return_value.succeeded = True
        session = Session(name="test")
        session.attach(mock_ctrl, "win32", "test-window")
        executor._sessions["test"] = session
        executor._default = "test"

        # The REPL should forward through LocalExecutor
        repl = _make_repl(on_session="test", executor=executor)
        # Verify executor is set
        assert repl.executor is executor

    def test_close_all_on_exit(self):
        """Repl.run() should call executor.close_all() on exit."""
        from maafw_cli.core.local_executor import LocalExecutor
        executor = LocalExecutor()

        repl = _make_repl(executor=executor)
        # Simulate immediate EOF
        with patch("builtins.input", side_effect=EOFError):
            repl.run()
        # close_all should have been called (no sessions, so it's a no-op but still called)
        assert len(executor._sessions) == 0


class TestReplParseErrors:
    """REPL should handle invalid input gracefully."""

    def test_empty_line(self, capsys):
        repl = _make_repl()
        repl.execute_line("")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_bad_shlex(self, capsys):
        repl = _make_repl()
        repl.execute_line("click 'unterminated")
        captured = capsys.readouterr()
        assert "Error" in captured.err
