"""CLI integration tests using Click's CliRunner.

These test the CLI layer in isolation — MaaFW calls are not executed
(would need a real device). We test:
- Command structure and help text
- Global options parsing
- Output format selection
"""
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
        assert "list" in result.output

    def test_device_list_help(self):
        result = runner.invoke(cli, ["device", "list", "--help"])
        assert result.exit_code == 0
        assert "--adb" in result.output

    def test_connect_help(self):
        result = runner.invoke(cli, ["connect", "--help"])
        assert result.exit_code == 0
        assert "adb" in result.output

    def test_connect_adb_help(self):
        result = runner.invoke(cli, ["connect", "adb", "--help"])
        assert result.exit_code == 0
        assert "DEVICE" in result.output
        assert "--screenshot-size" in result.output

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
        assert "--long" in result.output

    def test_global_json_flag(self):
        """Ensure --json is accepted as a global option."""
        result = runner.invoke(cli, ["--json", "--help"])
        assert result.exit_code == 0

    def test_global_quiet_flag(self):
        """Ensure --quiet is accepted as a global option."""
        result = runner.invoke(cli, ["--quiet", "--help"])
        assert result.exit_code == 0


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
