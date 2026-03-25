"""Tests for daemon logging configuration."""
from __future__ import annotations

import os

from maafw_cli.daemon.log import setup_daemon_logging


class TestDaemonLogging:
    def test_no_truncation_on_setup(self, tmp_path, monkeypatch):
        """setup_daemon_logging should NOT truncate the existing log file."""
        monkeypatch.setattr("maafw_cli.daemon.log._data_dir", lambda: tmp_path)

        log_file = tmp_path / "daemon.log"
        log_file.write_text("previous log content\n", encoding="utf-8")

        logger = setup_daemon_logging()
        content = log_file.read_text(encoding="utf-8")
        assert "previous log content" in content
        logger.handlers.clear()

    def test_startup_banner_includes_pid(self, tmp_path, monkeypatch):
        """Startup banner should include the current PID."""
        monkeypatch.setattr("maafw_cli.daemon.log._data_dir", lambda: tmp_path)

        logger = setup_daemon_logging()
        content = (tmp_path / "daemon.log").read_text(encoding="utf-8")
        assert f"PID={os.getpid()}" in content
        logger.handlers.clear()
