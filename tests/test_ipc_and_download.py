"""Tests for get_daemon_info() and check_ocr_files_exist / download logic."""
from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── get_daemon_info ──────────────────────────────────────────────


class TestGetDaemonInfo:
    def test_returns_none_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        from maafw_cli.core.ipc import get_daemon_info
        pid, port = get_daemon_info()
        assert pid is None
        assert port is None

    def test_returns_none_when_process_dead(self, tmp_path, monkeypatch):
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        (tmp_path / "daemon.pid").write_text("999999999")
        (tmp_path / "daemon.port").write_text("19799")
        from maafw_cli.core.ipc import get_daemon_info
        pid, port = get_daemon_info()
        assert pid is None
        assert port is None

    def test_returns_pid_port_when_alive(self, tmp_path, monkeypatch):
        import os
        monkeypatch.setattr("maafw_cli.core.ipc._data_dir", lambda: tmp_path)
        my_pid = os.getpid()
        (tmp_path / "daemon.pid").write_text(str(my_pid))
        (tmp_path / "daemon.port").write_text("19800")
        from maafw_cli.core.ipc import get_daemon_info
        pid, port = get_daemon_info()
        assert pid == my_pid
        assert port == 19800


# ── check_ocr_files_exist ───────────────────────────────────────


class TestCheckOcrFiles:
    def test_all_files_present(self, tmp_path):
        from maafw_cli.download import check_ocr_files_exist, OCR_REQUIRED_FILES
        for f in OCR_REQUIRED_FILES:
            (tmp_path / f).write_text("dummy")
        assert check_ocr_files_exist(tmp_path) is True

    def test_partial_files(self, tmp_path):
        from maafw_cli.download import check_ocr_files_exist, OCR_REQUIRED_FILES
        # Only create first file
        (tmp_path / OCR_REQUIRED_FILES[0]).write_text("dummy")
        assert check_ocr_files_exist(tmp_path) is False

    def test_no_files(self, tmp_path):
        from maafw_cli.download import check_ocr_files_exist
        assert check_ocr_files_exist(tmp_path) is False

    def test_empty_dir(self, tmp_path):
        from maafw_cli.download import check_ocr_files_exist
        empty = tmp_path / "empty"
        empty.mkdir()
        assert check_ocr_files_exist(empty) is False


# ── download_and_extract_ocr ────────────────────────────────────


def _make_test_zip(zip_path: Path, files: dict[str, bytes]) -> None:
    """Create a zip file with the given {name: content} entries."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


class TestDownloadAndExtract:
    def test_success(self, tmp_path, monkeypatch):
        from maafw_cli.download import download_and_extract_ocr, OCR_REQUIRED_FILES

        ocr_dir = tmp_path / "ocr"
        model_dir = tmp_path / "model"
        monkeypatch.setattr("maafw_cli.download.get_model_dir", lambda: model_dir)

        # Build a small zip with the required files
        test_zip = tmp_path / "test.zip"
        files = {f: b"fake model data" for f in OCR_REQUIRED_FILES}
        _make_test_zip(test_zip, files)

        # Mock urlopen to return our test zip
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": str(test_zip.stat().st_size)}
        mock_response.read.side_effect = [
            test_zip.read_bytes(),  # first read: all content
            b"",                     # second read: EOF
        ]
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *a: None

        with patch("maafw_cli.download.urlopen", return_value=mock_response):
            result = download_and_extract_ocr(ocr_dir)

        assert result is True
        for f in OCR_REQUIRED_FILES:
            assert (ocr_dir / f).exists()

    def test_network_error(self, tmp_path, monkeypatch):
        from urllib.error import URLError
        from maafw_cli.download import download_and_extract_ocr

        ocr_dir = tmp_path / "ocr"
        model_dir = tmp_path / "model"
        monkeypatch.setattr("maafw_cli.download.get_model_dir", lambda: model_dir)

        with patch("maafw_cli.download.urlopen", side_effect=URLError("timeout")):
            result = download_and_extract_ocr(ocr_dir)

        assert result is False

    def test_bad_zip(self, tmp_path, monkeypatch):
        from maafw_cli.download import download_and_extract_ocr

        ocr_dir = tmp_path / "ocr"
        model_dir = tmp_path / "model"
        monkeypatch.setattr("maafw_cli.download.get_model_dir", lambda: model_dir)

        # Mock urlopen to return garbage (not a zip)
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "10"}
        mock_response.read.side_effect = [b"not a zip!", b""]
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *a: None

        with patch("maafw_cli.download.urlopen", return_value=mock_response):
            result = download_and_extract_ocr(ocr_dir)

        assert result is False

    def test_missing_files_in_zip(self, tmp_path, monkeypatch):
        """Zip that lacks required files should return False."""
        from maafw_cli.download import download_and_extract_ocr

        ocr_dir = tmp_path / "ocr"
        model_dir = tmp_path / "model"
        monkeypatch.setattr("maafw_cli.download.get_model_dir", lambda: model_dir)

        # Build a zip with only one of the required files (missing det.onnx and rec.onnx)
        test_zip = tmp_path / "test.zip"
        _make_test_zip(test_zip, {"keys.txt": b"fake keys"})

        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": str(test_zip.stat().st_size)}
        mock_response.read.side_effect = [test_zip.read_bytes(), b""]
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = lambda s, *a: None

        with patch("maafw_cli.download.urlopen", return_value=mock_response):
            result = download_and_extract_ocr(ocr_dir)

        assert result is False
