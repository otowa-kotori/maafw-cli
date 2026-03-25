"""Tests for core logging setup and Timer context manager."""
from __future__ import annotations

import logging
import time

from maafw_cli.core.log import setup_logging, Timer, logger


class TestSetupLogging:
    def test_default_level_info(self):
        setup_logging()
        assert logger.level == logging.INFO

    def test_verbose_level_debug(self):
        setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_quiet_level_warning(self):
        setup_logging(quiet=True)
        assert logger.level == logging.WARNING

    def test_handlers_cleared_on_reconfig(self):
        setup_logging()
        n1 = len(logger.handlers)
        setup_logging()
        n2 = len(logger.handlers)
        assert n1 == n2 == 1  # always exactly one handler


class TestTimer:
    def test_elapsed_ms(self):
        with Timer("test") as t:
            time.sleep(0.05)
        assert t.elapsed_ms >= 40  # at least ~50ms minus jitter

    def test_label_logged(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="maafw_cli"):
            with Timer("my_block"):
                pass
        assert any("my_block" in r.message for r in caplog.records)
