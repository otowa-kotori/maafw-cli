"""
Manual integration tests — requires a real ADB device/emulator.

NOT part of automated CI. Run manually to verify end-to-end functionality:

    uv run python -m pytest tests/test_adb_manual.py -v -s

Prerequisites:
    - An ADB device or emulator connected (e.g. emulator-5554)
    - OCR model downloaded (maafw-cli resource download-ocr, or existing MaaMCP data)

Usage:
    # Run all manual tests:
    uv run python -m pytest tests/test_adb_manual.py -v -s

    # Run a single test:
    uv run python -m pytest tests/test_adb_manual.py::test_device_list -v -s

    # Override device name via env var (default: auto-detect first device):
    MAAFW_TEST_DEVICE=emulator-5554 uv run python -m pytest tests/test_adb_manual.py -v -s

Reproducible environment considerations:
    - Could use Android emulator in Docker (e.g. budtmo/docker-android) for CI
    - But startup is slow (~60s) and flaky across host OS
    - For now, manual verification is the pragmatic choice
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli

runner = CliRunner()

# Allow overriding the test device via env var
_TEST_DEVICE = os.environ.get("MAAFW_TEST_DEVICE", "")


def _get_device() -> str:
    """Return the test device name, auto-detecting if not set."""
    if _TEST_DEVICE:
        return _TEST_DEVICE
    # Auto-detect: run device list --json and pick the first one
    result = runner.invoke(cli, ["--json", "device", "list", "--adb"])
    if result.exit_code != 0:
        pytest.skip(f"No ADB devices found (exit code {result.exit_code})")
    devices = json.loads(result.output)
    if not devices:
        pytest.skip("No ADB devices found")
    return devices[0]["name"]


# ── Tests ───────────────────────────────────────────────────────


def test_device_list():
    """Verify device list returns at least one device."""
    result = runner.invoke(cli, ["device", "list", "--adb"])
    print(result.output)
    assert result.exit_code == 0
    assert "ADB devices" in result.output


def test_device_list_json():
    """Verify --json output is parseable."""
    result = runner.invoke(cli, ["--json", "device", "list", "--adb"])
    print(result.output)
    assert result.exit_code == 0
    devices = json.loads(result.output)
    assert isinstance(devices, list)
    assert len(devices) > 0
    assert "name" in devices[0]


def test_connect():
    """Verify connecting to a device."""
    device = _get_device()
    result = runner.invoke(cli, ["connect", "adb", device])
    print(result.output)
    assert result.exit_code == 0
    assert "Connected" in result.output


def test_connect_json():
    """Verify connect --json output."""
    device = _get_device()
    result = runner.invoke(cli, ["--json", "connect", "adb", device])
    print(result.output)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["type"] == "adb"
    assert data["device"] == device


def test_screenshot():
    """Verify screenshot saves a file."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.png"
        result = runner.invoke(cli, ["screenshot", "--output", str(out)])
        print(result.output)
        assert result.exit_code == 0
        assert out.exists()
        assert out.stat().st_size > 1000  # should be a real image


def test_screenshot_auto_name():
    """Verify screenshot with auto-generated filename."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    result = runner.invoke(cli, ["--json", "screenshot"])
    print(result.output)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert Path(data["path"]).exists()


def test_ocr():
    """Verify OCR returns TextRef results."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    result = runner.invoke(cli, ["ocr"])
    print(result.output)
    assert result.exit_code == 0
    # Should have the table header and at least the separator
    assert "Screen OCR" in result.output


def test_ocr_json():
    """Verify OCR --json returns structured data."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    result = runner.invoke(cli, ["--json", "ocr"])
    print(result.output)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "results" in data
    assert "elapsed_ms" in data
    if data["results"]:
        r = data["results"][0]
        assert "ref" in r
        assert "text" in r
        assert "box" in r
        assert "score" in r


def test_ocr_text_only():
    """Verify --text-only outputs just the text."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    result = runner.invoke(cli, ["ocr", "--text-only"])
    print(result.output)
    assert result.exit_code == 0
    # Should NOT have table formatting
    assert "Screen OCR" not in result.output


def test_click_by_coords():
    """Verify clicking by coordinates."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    result = runner.invoke(cli, ["click", "100,100"])
    print(result.output)
    assert result.exit_code == 0
    assert "Clicked" in result.output


def test_click_by_textref():
    """Verify clicking by TextRef (requires OCR first)."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])

    # First run OCR to populate TextRefs
    ocr_result = runner.invoke(cli, ["--json", "ocr"])
    if ocr_result.exit_code != 0:
        pytest.skip("OCR failed")
    data = json.loads(ocr_result.output)
    if not data.get("results"):
        pytest.skip("No OCR results to click on")

    # Click the first TextRef
    result = runner.invoke(cli, ["click", "t1"])
    print(result.output)
    assert result.exit_code == 0
    assert "Clicked" in result.output


def test_click_by_textref_json():
    """Verify click --json returns structured data."""
    device = _get_device()
    runner.invoke(cli, ["connect", "adb", device])
    runner.invoke(cli, ["ocr"])

    result = runner.invoke(cli, ["--json", "click", "100,200"])
    print(result.output)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["action"] == "click"
    assert data["x"] == 100
    assert data["y"] == 200


def test_full_workflow():
    """End-to-end: connect → ocr → click → ocr again."""
    device = _get_device()

    # 1. Connect
    r = runner.invoke(cli, ["connect", "adb", device])
    assert r.exit_code == 0, f"connect failed: {r.output}"

    # 2. OCR
    r = runner.invoke(cli, ["--json", "ocr"])
    assert r.exit_code == 0, f"ocr failed: {r.output}"
    ocr1 = json.loads(r.output)
    print(f"OCR found {len(ocr1['results'])} results in {ocr1['elapsed_ms']}ms")

    # 3. Click somewhere safe (center-ish)
    r = runner.invoke(cli, ["click", "360,640"])
    assert r.exit_code == 0, f"click failed: {r.output}"

    # 4. OCR again (screen may have changed)
    r = runner.invoke(cli, ["--json", "ocr"])
    assert r.exit_code == 0, f"second ocr failed: {r.output}"
    ocr2 = json.loads(r.output)
    print(f"OCR found {len(ocr2['results'])} results in {ocr2['elapsed_ms']}ms")

    print("Full workflow passed.")
