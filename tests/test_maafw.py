"""Tests for maafw/ wrappers — init_toolkit, vision helpers."""
from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

from maafw_cli.maafw import init_toolkit


class TestInitToolkit:
    def test_logs_warning_on_failure(self, caplog):
        """init_toolkit() should log a warning when MaaFramework init fails."""
        with patch.dict("sys.modules", {"maa.toolkit": MagicMock()}):
            mock_toolkit = sys.modules["maa.toolkit"]
            mock_toolkit.Toolkit.init_option.side_effect = RuntimeError("no DLL")

            with caplog.at_level(logging.WARNING, logger="maafw_cli.maafw"):
                init_toolkit()

            assert any("Failed to initialize" in r.message for r in caplog.records)


class TestOcrNodesBoundary:
    def test_empty_nodes_returns_none(self):
        """ocr() should return None when info.nodes is empty, not IndexError."""
        from maafw_cli.maafw import vision

        mock_controller = MagicMock()

        with patch.object(vision, "check_ocr_files_exist", return_value=True), \
             patch.object(vision, "_get_tasker") as mock_tasker, \
             patch.object(vision, "screencap", return_value="fake_image"):

            mock_detail = MagicMock()
            mock_detail.nodes = []

            mock_tasker_inst = mock_tasker.return_value
            mock_tasker_inst.post_recognition.return_value.wait.return_value.get.return_value = mock_detail

            result = vision.ocr(mock_controller)
            assert result is None
