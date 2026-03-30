"""CLI integration tests using Click's CliRunner.

These test the CLI layer in isolation — MaaFW calls are not executed
(would need a real device). We test:
- Command structure and help text
- Global options parsing
- Output format selection
"""
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli


runner = CliRunner()


class TestCliStructure:
    """Verify the command tree is wired correctly."""

    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "maafw-cli" in result.output

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_device_help(self):
        result = runner.invoke(cli, ["device", "--help"])
        assert result.exit_code == 0
        assert "adb" in result.output
        assert "win32" in result.output
        assert "all" in result.output

    def test_connect_help(self):
        result = runner.invoke(cli, ["connect", "--help"])
        assert result.exit_code == 0
        assert "adb" in result.output
        assert "win32" in result.output

    def test_connect_adb_help(self):
        result = runner.invoke(cli, ["connect", "adb", "--help"])
        assert result.exit_code == 0
        assert "DEVICE" in result.output
        assert "--size" in result.output

    def test_connect_win32_help(self):
        result = runner.invoke(cli, ["connect", "win32", "--help"])
        assert result.exit_code == 0
        assert "WINDOW" in result.output

    def test_ocr_help(self):
        result = runner.invoke(cli, ["ocr", "--help"])
        assert result.exit_code == 0
        assert "--json" not in result.output  # json is on root group
        assert "--roi" in result.output
        assert "--text-only" in result.output

    def test_screenshot_help(self):
        result = runner.invoke(cli, ["screenshot", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_click_help(self):
        result = runner.invoke(cli, ["click", "--help"])
        assert result.exit_code == 0
        assert "TARGET" in result.output

    def test_swipe_help(self):
        result = runner.invoke(cli, ["swipe", "--help"])
        assert result.exit_code == 0
        assert "FROM" in result.output
        assert "TO" in result.output
        assert "--duration" in result.output

    def test_scroll_help(self):
        result = runner.invoke(cli, ["scroll", "--help"])
        assert result.exit_code == 0
        assert "DX" in result.output
        assert "DY" in result.output

    def test_type_help(self):
        result = runner.invoke(cli, ["type", "--help"])
        assert result.exit_code == 0
        assert "TEXT" in result.output

    def test_key_help(self):
        result = runner.invoke(cli, ["key", "--help"])
        assert result.exit_code == 0
        assert "KEYCODE" in result.output

    def test_repl_help(self):
        result = runner.invoke(cli, ["repl", "--help"])
        assert result.exit_code == 0

    def test_resource_help(self):
        result = runner.invoke(cli, ["resource", "--help"])
        assert result.exit_code == 0
        assert "download-ocr" in result.output
        assert "status" in result.output

    def test_resource_download_ocr_help(self):
        result = runner.invoke(cli, ["resource", "download-ocr", "--help"])
        assert result.exit_code == 0

    def test_resource_status_help(self):
        result = runner.invoke(cli, ["resource", "status", "--help"])
        assert result.exit_code == 0

    def test_global_json_flag(self):
        """Ensure --json is accepted as a global option."""
        result = runner.invoke(cli, ["--json", "--help"])
        assert result.exit_code == 0

    def test_global_quiet_flag(self):
        """Ensure --quiet is accepted as a global option."""
        result = runner.invoke(cli, ["--quiet", "--help"])
        assert result.exit_code == 0

    # ── Phase 3: daemon / session commands ──────────────────────

    def test_daemon_help(self):
        result = runner.invoke(cli, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output
        assert "restart" in result.output
        assert "status" in result.output

    def test_daemon_start_help(self):
        result = runner.invoke(cli, ["daemon", "start", "--help"])
        assert result.exit_code == 0

    def test_daemon_stop_help(self):
        result = runner.invoke(cli, ["daemon", "stop", "--help"])
        assert result.exit_code == 0

    def test_daemon_status_help(self):
        result = runner.invoke(cli, ["daemon", "status", "--help"])
        assert result.exit_code == 0

    def test_daemon_restart_help(self):
        result = runner.invoke(cli, ["daemon", "restart", "--help"])
        assert result.exit_code == 0

    def test_session_help(self):
        result = runner.invoke(cli, ["session", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "default" in result.output
        assert "close" in result.output

    def test_session_list_help(self):
        result = runner.invoke(cli, ["session", "list", "--help"])
        assert result.exit_code == 0

    def test_session_default_help(self):
        result = runner.invoke(cli, ["session", "default", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output

    def test_session_close_help(self):
        result = runner.invoke(cli, ["session", "close", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output

    def test_global_on_flag(self):
        result = runner.invoke(cli, ["--on", "phone", "--help"])
        assert result.exit_code == 0

    def test_connect_adb_has_on_option(self):
        result = runner.invoke(cli, ["connect", "adb", "--help"])
        assert result.exit_code == 0

    def test_connect_win32_has_on_option(self):
        result = runner.invoke(cli, ["connect", "win32", "--help"])
        assert result.exit_code == 0

    # ── GlobalOptionGroup: global options at any position ─────

    def test_on_after_subcommand(self):
        """--on should work after the subcommand name."""
        result = runner.invoke(cli, ["connect", "adb", "--help", "--on", "phone"])
        assert result.exit_code == 0

    def test_on_after_nested_subcommand(self):
        """--on should work after a nested subcommand like 'connect adb'."""
        result = runner.invoke(cli, ["connect", "win32", "--help", "--on", "game"])
        assert result.exit_code == 0

    def test_json_after_subcommand(self):
        """--json should work after the subcommand name."""
        result = runner.invoke(cli, ["ocr", "--help", "--json"])
        assert result.exit_code == 0

    def test_multiple_globals_after_subcommand(self):
        """Multiple global options after the subcommand."""
        result = runner.invoke(cli, ["click", "--help", "--on", "x", "--json"])
        assert result.exit_code == 0

    def test_global_mixed_with_subcommand_options(self):
        """--on mixed with subcommand-specific options."""
        result = runner.invoke(cli, ["connect", "adb", "--help", "--on", "phone"])
        assert result.exit_code == 0
        assert "DEVICE" in result.output


class TestOutputFormatter:
    """Test the output formatter directly."""

    def test_human_mode(self, capsys):
        from maafw_cli.core.output import OutputFormatter
        fmt = OutputFormatter(json_mode=False, quiet=False)
        fmt.success({"key": "val"}, human="Hello world")
        captured = capsys.readouterr()
        assert "Hello world" in captured.out

    def test_json_mode(self, capsys):
        from maafw_cli.core.output import OutputFormatter
        import json
        fmt = OutputFormatter(json_mode=True, quiet=False)
        fmt.success({"key": "val"}, human="Hello world")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "val"

    def test_quiet_mode(self, capsys):
        from maafw_cli.core.output import OutputFormatter
        fmt = OutputFormatter(json_mode=False, quiet=True)
        fmt.success({"key": "val"}, human="Hello world")
        captured = capsys.readouterr()
        assert captured.out == ""


class TestKeyResolver:
    """Test the key name → keycode resolver (dual keymap)."""

    # ── Win32 (default) ──────────────────────────────────────────

    def test_win32_enter(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("enter", "win32") == 0x0D

    def test_win32_case_insensitive(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("ENTER", "win32") == 0x0D
        assert resolve_keycode("Enter", "win32") == 0x0D

    def test_win32_tab(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("tab", "win32") == 0x09

    def test_win32_esc(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("esc", "win32") == 0x1B
        assert resolve_keycode("escape", "win32") == 0x1B

    def test_win32_f1(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("f1", "win32") == 0x70

    def test_win32_f12(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("f12", "win32") == 0x7B

    def test_win32_space(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("space", "win32") == 0x20

    # ── ADB / Android ────────────────────────────────────────────

    def test_adb_enter(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("enter", "adb") == 66

    def test_adb_back(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("back", "adb") == 4

    def test_adb_home(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("home", "adb") == 3

    def test_adb_tab(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("tab", "adb") == 61

    def test_adb_space(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("space", "adb") == 62

    def test_adb_esc(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("esc", "adb") == 111

    def test_adb_volume_up(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("volume_up", "adb") == 24

    def test_adb_f5(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("f5", "adb") == 135

    # ── Raw integer passthrough (both platforms) ─────────────────

    def test_hex_literal(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("0x0D", "win32") == 0x0D
        assert resolve_keycode("0x0D", "adb") == 0x0D

    def test_decimal_literal(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("66", "adb") == 66
        assert resolve_keycode("13", "win32") == 13

    def test_unknown_key(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("nonexistent", "win32") is None
        assert resolve_keycode("nonexistent", "adb") is None

    # ── Platform-specific keys ───────────────────────────────────

    def test_back_only_on_adb(self):
        """'back' is Android-specific, not in Win32 map."""
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("back", "adb") == 4
        assert resolve_keycode("back", "win32") is None

    def test_default_session_type_is_win32(self):
        from maafw_cli.core.keymap import resolve_keycode
        assert resolve_keycode("enter") == 0x0D  # default = win32


# ── Daemon command output ────────────────────────────────────────


class TestDaemonCommands:
    def test_daemon_stop_says_shutdown_requested(self):
        """daemon stop should say 'Shutdown requested', not 'Daemon stopped'."""
        with patch("maafw_cli.core.ipc.get_daemon_info", return_value=(123, 19799)), \
             patch("maafw_cli.core.ipc.DaemonClient") as mock_client_cls:
            mock_client_cls.return_value.send.return_value = {}
            result = runner.invoke(cli, ["daemon", "stop"])
            assert "Shutdown requested" in result.output

    def test_daemon_status_unreachable_is_error(self):
        """daemon status should report unreachable as error, not success."""
        with patch("maafw_cli.core.ipc.get_daemon_info", return_value=(123, 19799)), \
             patch("maafw_cli.core.ipc.DaemonClient") as mock_client_cls:
            mock_client_cls.return_value.send.side_effect = OSError("refused")
            result = runner.invoke(cli, ["daemon", "status"])
            assert result.exit_code == 3
            assert "unreachable" in result.output.lower()


# ── Device all command ────────────────────────────────────────


class TestDeviceAll:
    """Test device all when one source is empty."""

    def _make_ctx(self):
        """Build a mock CliContext with a real OutputFormatter."""
        from maafw_cli.core.output import OutputFormatter
        ctx = MagicMock()
        ctx.fmt = OutputFormatter(json_mode=False, quiet=False)
        return ctx

    def test_device_all_only_adb(self):
        """device all should succeed when only ADB has results."""
        from maafw_cli.commands.connection import _device_list

        ctx = self._make_ctx()
        ctx.run_raw.return_value = {
            "adb": [{"name": "device1", "address": "127.0.0.1:5555"}],
            "win32": [],
        }
        # Should not call sys.exit (no error)
        _device_list(ctx, adb_flag=True, win32_flag=True)

    def test_device_all_only_win32(self):
        """device all should succeed when only Win32 has results."""
        from maafw_cli.commands.connection import _device_list

        ctx = self._make_ctx()
        ctx.run_raw.return_value = {
            "adb": [],
            "win32": [{"hwnd": "0x1234", "window_name": "Test", "class_name": "Cls"}],
        }
        _device_list(ctx, adb_flag=True, win32_flag=True)

    def test_device_all_both_empty(self):
        """device all should fail when both sides are empty."""
        from maafw_cli.commands.connection import _device_list

        ctx = self._make_ctx()
        ctx.run_raw.return_value = {"adb": [], "win32": []}
        with pytest.raises(SystemExit) as exc_info:
            _device_list(ctx, adb_flag=True, win32_flag=True)
        assert exc_info.value.code == 3
