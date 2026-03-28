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
    def _make_session(self):
        """Create a mock Session with the interface ocr() expects."""
        session = MagicMock()
        session.controller = MagicMock()
        return session

    def test_empty_nodes_raises_recognition_error(self):
        """ocr() should raise RecognitionError when info.nodes is empty."""
        from maafw_cli.maafw import vision

        session = self._make_session()
        mock_detail = MagicMock()
        mock_detail.nodes = []
        session.get_tasker.return_value.post_recognition.return_value.wait.return_value.get.return_value = mock_detail

        with patch.object(vision, "check_ocr_files_exist", return_value=True), \
             patch.object(vision, "screencap", return_value="fake_image"):
            with pytest.raises(RecognitionError, match="empty nodes"):
                vision.ocr(session)

    def test_no_ocr_model_raises(self):
        """ocr() should raise RecognitionError when OCR model is missing."""
        from maafw_cli.maafw import vision

        with patch.object(vision, "check_ocr_files_exist", return_value=False):
            with pytest.raises(RecognitionError, match="OCR model not found"):
                vision.ocr(self._make_session())

    def test_screenshot_failure_raises(self):
        """ocr() should raise RecognitionError when screenshot fails."""
        from maafw_cli.maafw import vision

        session = self._make_session()
        session.get_tasker.return_value = MagicMock()

        with patch.object(vision, "check_ocr_files_exist", return_value=True), \
             patch.object(vision, "screencap", return_value=None):
            with pytest.raises(RecognitionError, match="Screenshot failed"):
                vision.ocr(session)

    def test_tasker_init_failure_raises(self):
        """ocr() should raise RecognitionError when tasker fails to init."""
        from maafw_cli.maafw import vision

        session = self._make_session()
        session.get_tasker.return_value = None

        with patch.object(vision, "check_ocr_files_exist", return_value=True):
            with pytest.raises(RecognitionError, match="tasker"):
                vision.ocr(session)
