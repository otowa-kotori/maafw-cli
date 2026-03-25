"""Tests for maafw/ wrappers — init_toolkit, vision helpers."""
from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import RecognitionError
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


class TestOcrFailureExceptions:
    def test_empty_nodes_raises_recognition_error(self):
        """ocr() should raise RecognitionError when info.nodes is empty."""
        from maafw_cli.maafw import vision

        mock_controller = MagicMock()

        with patch.object(vision, "check_ocr_files_exist", return_value=True), \
             patch.object(vision, "_get_tasker") as mock_tasker, \
             patch.object(vision, "screencap", return_value="fake_image"):

            mock_detail = MagicMock()
            mock_detail.nodes = []

            mock_tasker_inst = mock_tasker.return_value
            mock_tasker_inst.post_recognition.return_value.wait.return_value.get.return_value = mock_detail

            with pytest.raises(RecognitionError, match="empty nodes"):
                vision.ocr(mock_controller)

    def test_no_ocr_model_raises(self):
        """ocr() should raise RecognitionError when OCR model is missing."""
        from maafw_cli.maafw import vision

        with patch.object(vision, "check_ocr_files_exist", return_value=False):
            with pytest.raises(RecognitionError, match="OCR model not found"):
                vision.ocr(MagicMock())

    def test_screenshot_failure_raises(self):
        """ocr() should raise RecognitionError when screenshot fails."""
        from maafw_cli.maafw import vision

        with patch.object(vision, "check_ocr_files_exist", return_value=True), \
             patch.object(vision, "_get_tasker", return_value=MagicMock()), \
             patch.object(vision, "screencap", return_value=None):
            with pytest.raises(RecognitionError, match="Screenshot failed"):
                vision.ocr(MagicMock())

    def test_tasker_init_failure_raises(self):
        """ocr() should raise RecognitionError when tasker fails to init."""
        from maafw_cli.maafw import vision

        with patch.object(vision, "check_ocr_files_exist", return_value=True), \
             patch.object(vision, "_get_tasker", return_value=None):
            with pytest.raises(RecognitionError, match="tasker"):
                vision.ocr(MagicMock())
