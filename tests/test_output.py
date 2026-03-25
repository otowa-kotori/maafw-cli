"""Tests for OutputFormatter — format_ocr_table, print_error, error."""
from __future__ import annotations

import io
import sys
from unittest.mock import patch

import pytest

from maafw_cli.core.output import OutputFormatter


class TestFormatOcrTable:
    def test_basic(self):
        refs = [
            {"ref": "e1", "text": "Hello", "box": [10, 20, 100, 30], "score": 0.95},
            {"ref": "e2", "text": "World", "box": [10, 60, 100, 30], "score": 0.88},
        ]
        result = OutputFormatter.format_ocr_table(refs, 123)
        assert "e1" in result
        assert "Hello" in result
        assert "e2" in result
        assert "World" in result
        assert "95%" in result
        assert "88%" in result
        assert "2 results" in result
        assert "123ms" in result
        assert "default" in result  # default session label

    def test_custom_session_label(self):
        refs = [{"ref": "e1", "text": "x", "box": [0, 0, 1, 1], "score": 1.0}]
        result = OutputFormatter.format_ocr_table(refs, 50, session_label="phone")
        assert "phone" in result

    def test_empty_refs(self):
        result = OutputFormatter.format_ocr_table([], 0)
        assert "0 results" in result
        assert "0ms" in result

    def test_unicode_text(self):
        refs = [{"ref": "e1", "text": "设置", "box": [10, 20, 80, 24], "score": 0.97}]
        result = OutputFormatter.format_ocr_table(refs, 200)
        assert "设置" in result
        assert "97%" in result


class TestPrintError:
    def test_print_error_stderr(self):
        fmt = OutputFormatter()
        buf = io.BytesIO()
        mock_stderr = type("FakeStderr", (), {"buffer": buf})()
        with patch.object(sys, "stderr", mock_stderr):
            fmt.print_error("something broke")
        output = buf.getvalue().decode("utf-8")
        assert "Error: something broke" in output

    def test_print_error_json_mode(self, capsys):
        fmt = OutputFormatter(json_mode=True)
        # JSON error goes to stdout
        buf = io.BytesIO()
        mock_stdout = type("FakeStdout", (), {"buffer": buf})()
        with patch.object(sys, "stdout", mock_stdout):
            fmt.print_error("json error")
        output = buf.getvalue().decode("utf-8")
        assert '"error"' in output
        assert "json error" in output

    def test_print_error_quiet_mode(self):
        fmt = OutputFormatter(quiet=True)
        buf = io.BytesIO()
        mock_stderr = type("FakeStderr", (), {"buffer": buf})()
        with patch.object(sys, "stderr", mock_stderr):
            fmt.print_error("should be silent")
        assert buf.getvalue() == b""


class TestErrorExits:
    def test_error_exits_with_code(self):
        fmt = OutputFormatter(quiet=True)
        with pytest.raises(SystemExit) as exc_info:
            fmt.error("fatal", exit_code=3)
        assert exc_info.value.code == 3

    def test_error_exits_default_code_1(self):
        fmt = OutputFormatter(quiet=True)
        with pytest.raises(SystemExit) as exc_info:
            fmt.error("fatal")
        assert exc_info.value.code == 1


class TestOutputNoBuf:
    """OutputFormatter must work when stdout/stderr lack .buffer (e.g. StringIO)."""

    def test_print_text_no_buffer(self):
        fmt = OutputFormatter()
        sio = io.StringIO()
        fmt._print_text("hello 你好", file=sio)
        assert sio.getvalue() == "hello 你好\n"

    def test_print_json_no_buffer(self):
        fmt = OutputFormatter()
        sio = io.StringIO()
        with patch.object(sys, "stdout", sio):
            fmt._print_json({"key": "值"})
        output = sio.getvalue()
        assert '"key"' in output
        assert "值" in output

    def test_success_human_no_buffer(self):
        fmt = OutputFormatter()
        sio = io.StringIO()
        with patch.object(sys, "stdout", sio):
            fmt.success({"a": 1}, human="OK 成功")
        assert "OK 成功" in sio.getvalue()

    def test_print_error_no_buffer(self):
        fmt = OutputFormatter()
        sio = io.StringIO()
        with patch.object(sys, "stderr", sio):
            fmt.print_error("bad thing")
        assert "Error: bad thing" in sio.getvalue()


class TestFormatRecoTable:
    def test_template_match_output(self):
        refs = [{"ref": "e1", "text": None, "box": [10, 20, 100, 30], "score": 0.95}]
        result = OutputFormatter.format_reco_table(refs, 150, "TemplateMatch")
        assert "e1" in result
        assert "TemplateMatch" in result
        assert "95%" in result
        assert "150ms" in result
        assert "1 results" in result

    def test_color_match_output_shows_count(self):
        refs = [{"ref": "e1", "text": None, "box": [10, 20, 100, 30], "score": 0.0, "count": 1542}]
        result = OutputFormatter.format_reco_table(refs, 80, "ColorMatch")
        assert "count=1542" in result
        assert "ColorMatch" in result

    def test_ocr_type_shows_text_and_score(self):
        refs = [{"ref": "e1", "text": "设置", "box": [10, 20, 80, 24], "score": 0.97}]
        result = OutputFormatter.format_reco_table(refs, 200, "OCR")
        assert "设置" in result
        assert "97%" in result
        assert "OCR" in result

    def test_custom_session_label(self):
        refs = [{"ref": "e1", "text": None, "box": [0, 0, 1, 1], "score": 0.5}]
        result = OutputFormatter.format_reco_table(refs, 50, "TemplateMatch", "phone")
        assert "phone" in result

    def test_empty_refs(self):
        result = OutputFormatter.format_reco_table([], 0, "TemplateMatch")
        assert "0 results" in result

    def test_multiple_results(self):
        refs = [
            {"ref": "e1", "text": None, "box": [10, 20, 30, 40], "score": 0.95},
            {"ref": "e2", "text": None, "box": [50, 60, 70, 80], "score": 0.88},
        ]
        result = OutputFormatter.format_reco_table(refs, 120, "TemplateMatch")
        assert "e1" in result
        assert "e2" in result
        assert "2 results" in result
