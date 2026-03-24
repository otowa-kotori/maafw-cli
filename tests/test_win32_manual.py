"""
Manual integration tests for Win32 window support.

The test session automatically launches a lightweight tkinter mock window
(``tests/mock_win32_window.py``) and tears it down afterwards.
The mock responds to SendMessage input, so we can verify click operations
actually take effect by checking that the label text changes from
"READY" to "CLICKED".

NOT part of automated CI.  Run manually:

    uv run python -m pytest tests/test_win32_manual.py -v -s -m manual
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli

pytestmark = [
    pytest.mark.manual,
    pytest.mark.skipif(sys.platform != "win32", reason="Win32 tests require Windows"),
]

runner = CliRunner(charset="utf-8")

_MOCK_SCRIPT = str(Path(__file__).parent / "mock_win32_window.py")


# ── fixtures ────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def mock_window():
    """Launch the mock tkinter window and return its window info dict.

    Yields ``{"hwnd": "0x...", "window_name": "MaafwTest_<token>", ...}``.
    Kills the process on teardown.
    """
    token = uuid.uuid4().hex[:8]
    expected_title = f"MaafwTest_{token}"

    proc = subprocess.Popen(
        [sys.executable, _MOCK_SCRIPT, token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Give tkinter a moment to create the window
    time.sleep(1.5)

    # Find it via device list
    window = None
    for _attempt in range(5):
        result = runner.invoke(cli, ["--json", "device", "list", "--win32"])
        if result.exit_code != 0:
            time.sleep(0.5)
            continue
        windows = _parse_json_output(result.output)
        for w in windows:
            if expected_title in w["window_name"]:
                window = w
                break
        if window:
            break
        time.sleep(0.5)

    if window is None:
        proc.kill()
        pytest.skip(f"Could not find mock window '{expected_title}' after launch")

    yield window

    proc.kill()
    proc.wait()


# ── helpers ─────────────────────────────────────────────────────


def _parse_json_output(output: str):
    """Extract JSON from CliRunner output that may have logger lines mixed in."""
    for i, ch in enumerate(output):
        if ch in ("[", "{"):
            return json.loads(output[i:])
    raise ValueError(f"No JSON found in output: {output[:200]}")


def _safe_print(text: str) -> None:
    """Print text safely on terminals that don't support full Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _ensure_connected(win: dict) -> None:
    """Connect to the mock window by hwnd."""
    result = runner.invoke(cli, ["connect", "win32", win["hwnd"]])
    if result.exit_code != 0:
        pytest.skip(f"Failed to connect (exit {result.exit_code})")


# ── Tests ───────────────────────────────────────────────────────


def test_win32_device_list():
    """Verify --win32 flag returns windows."""
    result = runner.invoke(cli, ["device", "list", "--win32"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Win32 windows" in result.output


def test_win32_device_list_json():
    """Verify --win32 --json output is parseable."""
    result = runner.invoke(cli, ["--json", "device", "list", "--win32"])
    _safe_print(result.output)
    assert result.exit_code == 0
    windows = _parse_json_output(result.output)
    assert isinstance(windows, list)
    assert len(windows) > 0
    w = windows[0]
    assert "hwnd" in w
    assert "window_name" in w
    assert "class_name" in w


def test_win32_connect_by_hwnd(mock_window):
    """Verify connecting by hwnd."""
    result = runner.invoke(cli, ["connect", "win32", mock_window["hwnd"]])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Connected" in result.output


def test_win32_connect_json(mock_window):
    """Verify connect win32 --json output."""
    result = runner.invoke(cli, ["--json", "connect", "win32", mock_window["hwnd"]])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert data["type"] == "win32"
    assert "window_name" in data
    assert "hwnd" in data


def test_win32_connect_not_found():
    """Verify error when window not found."""
    result = runner.invoke(cli, ["connect", "win32", "NONEXISTENT_WINDOW_12345"])
    _safe_print(result.output)
    assert result.exit_code == 3


def test_win32_connect_with_options(mock_window):
    """Verify --screencap-method and --input-method options."""
    result = runner.invoke(cli, [
        "connect", "win32", mock_window["hwnd"],
        "--screencap-method", "GDI",
        "--input-method", "Seize",
    ])
    _safe_print(result.output)
    assert result.exit_code == 0

    from maafw_cli.core.session import load_session
    from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum

    session = load_session()
    assert session.screencap_methods == int(MaaWin32ScreencapMethodEnum.GDI)
    assert session.input_methods == int(MaaWin32InputMethodEnum.Seize)


def test_win32_screenshot(mock_window):
    """Verify screenshot saves a file."""
    _ensure_connected(mock_window)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.png"
        result = runner.invoke(cli, ["screenshot", "--output", str(out)])
        _safe_print(result.output)
        assert result.exit_code == 0
        assert out.exists()
        assert out.stat().st_size > 1000  # should be a real image


def test_win32_screenshot_auto_name(mock_window):
    """Verify screenshot with auto-generated filename."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "screenshot"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert Path(data["path"]).exists()


def test_win32_ocr(mock_window):
    """Verify OCR returns results."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["ocr"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Screen OCR" in result.output


def test_win32_ocr_json(mock_window):
    """Verify OCR --json returns structured data."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "ocr"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert "results" in data
    assert "elapsed_ms" in data
    if data["results"]:
        r = data["results"][0]
        assert "ref" in r
        assert "text" in r
        assert "box" in r
        assert "score" in r


def test_win32_ocr_sees_ready(mock_window):
    """Verify OCR reads 'READY' from the mock window."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "ocr"])
    if result.exit_code != 0:
        pytest.skip("OCR failed")

    data = _parse_json_output(result.output)
    all_text = " ".join(r["text"] for r in data["results"])
    assert "READY" in all_text, f"Expected 'READY' in OCR output, got: {all_text}"


def test_win32_click_changes_label(mock_window):
    """Verify click actually works on the mock window.

    Connects with Seize input (highest compatibility), clicks the PRESS
    button, then verifies the label changes from READY to CLICKED.
    """
    # Connect with Seize — the only method that reliably works across
    # all Win32 window types (tkinter, UWP, etc.)
    result = runner.invoke(cli, [
        "connect", "win32", mock_window["hwnd"],
        "--input-method", "Seize",
    ])
    assert result.exit_code == 0

    # First OCR to locate the "PRESS" button
    result = runner.invoke(cli, ["--json", "ocr"])
    assert result.exit_code == 0
    data = _parse_json_output(result.output)

    # Find "PRESS" button coordinates
    btn = None
    for r in data["results"]:
        if "PRESS" in r["text"].upper():
            bx, by, bw, bh = r["box"]
            btn = (bx + bw // 2, by + bh // 2)
            break
    assert btn is not None, (
        f"Could not find 'PRESS' button in OCR. "
        f"Got: {[r['text'] for r in data['results']]}"
    )

    # Click the button
    result = runner.invoke(cli, ["click", f"{btn[0]},{btn[1]}"])
    _safe_print(result.output)
    assert result.exit_code == 0

    # Wait for UI update
    time.sleep(0.3)

    # OCR again — label should now say CLICKED
    result = runner.invoke(cli, ["--json", "ocr"])
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    all_text = " ".join(r["text"] for r in data["results"])
    assert "CLICKED" in all_text, (
        f"Expected 'CLICKED' after button press, got: {all_text}"
    )


def test_win32_session_persistence(mock_window):
    """Verify session is saved and can be reloaded."""
    _ensure_connected(mock_window)

    from maafw_cli.core.session import load_session

    session = load_session()
    assert session is not None
    assert session.type == "win32"
    assert session.window_name != ""
    assert session.address.startswith("0x")
    assert session.screencap_methods != 0
    assert session.input_methods != 0


def test_win32_reconnect(mock_window):
    """Verify reconnection works (via session file)."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["-v", "screenshot"])
    _safe_print(result.output)
    assert result.exit_code == 0


def test_win32_full_workflow(mock_window):
    """End-to-end: connect -> screenshot -> ocr -> click -> ocr again."""
    _ensure_connected(mock_window)

    # 1. Screenshot
    r = runner.invoke(cli, ["--json", "screenshot"])
    assert r.exit_code == 0, f"screenshot failed: {r.output}"
    data = _parse_json_output(r.output)
    assert Path(data["path"]).exists()
    print(f"Screenshot saved to {data['path']}")

    # 2. OCR
    r = runner.invoke(cli, ["--json", "ocr"])
    assert r.exit_code == 0, f"ocr failed: {r.output}"
    ocr1 = _parse_json_output(r.output)
    print(f"OCR found {len(ocr1['results'])} results in {ocr1['elapsed_ms']}ms")

    # 3. Click somewhere safe
    r = runner.invoke(cli, ["click", "100,100"])
    assert r.exit_code == 0, f"click failed: {r.output}"

    # 4. OCR again
    r = runner.invoke(cli, ["--json", "ocr"])
    assert r.exit_code == 0, f"second ocr failed: {r.output}"
    ocr2 = _parse_json_output(r.output)
    print(f"OCR found {len(ocr2['results'])} results in {ocr2['elapsed_ms']}ms")

    print("Full Win32 workflow passed.")
