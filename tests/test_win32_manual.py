"""
Automated integration tests for Win32 window support.

The test session automatically launches a lightweight tkinter mock window
(``tests/mock_win32_window.py``) and tears it down afterwards.
The mock responds to Seize input, so we can verify interactions
actually take effect by checking label text changes via OCR.

These tests run automatically on Windows (skipped on other platforms):

    uv run pytest tests/test_win32_manual.py -v -s

Tests are organized into three groups:

1. **Device discovery** — no connection needed, no mock_window fixture
2. **Daemon-mode tests** — default path, connect via daemon, operations via IPC
3. **Direct-mode tests** — ``--no-daemon``, verify file persistence (session.json)
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
        result = runner.invoke(cli, ["--json", "device", "win32"])
        if result.exit_code != 0:
            time.sleep(0.5)
            continue
        data = _parse_json_output(result.output)
        windows = data.get("win32", data) if isinstance(data, dict) else data
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

    # Stop daemon so the next test run starts clean
    runner.invoke(cli, ["daemon", "stop"])

    proc.kill()
    proc.wait()

    # Clean up auto-generated screenshot files
    import glob
    for f in glob.glob("screenshot_*.png"):
        try:
            Path(f).unlink()
        except OSError:
            pass


# ── helpers ─────────────────────────────────────────────────────


def _parse_json_output(output: str):
    """Extract JSON from CliRunner output that may have logger lines mixed in.

    Scans for the first ``[`` or ``{`` that starts valid JSON.  Retries from
    the next candidate if the first one fails (e.g. when info messages
    contain bracket characters).
    """
    i = 0
    while i < len(output):
        ch = output[i]
        if ch in ("[", "{"):
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                pass  # not valid JSON, keep scanning
        i += 1
    raise ValueError(f"No JSON found in output: {output[:200]}")


def _safe_print(text: str) -> None:
    """Print text safely on terminals that don't support full Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _ensure_connected(win: dict) -> None:
    """Connect to the mock window via daemon (default mode)."""
    result = runner.invoke(cli, ["connect", "win32", win["hwnd"]])
    if result.exit_code != 0:
        pytest.fail(f"Failed to connect (exit {result.exit_code}): {result.output.strip()}")


def _ensure_connected_seize(win: dict) -> None:
    """Connect with Seize input — the only method that triggers tkinter buttons."""
    result = runner.invoke(cli, [
        "connect", "win32", win["hwnd"],
        "--input-method", "Seize",
    ])
    if result.exit_code != 0:
        pytest.fail(f"Failed to connect with Seize (exit {result.exit_code}): {result.output.strip()}")


def _ensure_connected_direct(win: dict) -> None:
    """Connect in --no-daemon mode for file persistence tests."""
    result = runner.invoke(cli, [
        "--no-daemon", "connect", "win32", win["hwnd"],
    ])
    if result.exit_code != 0:
        pytest.fail(f"Failed to connect in direct mode (exit {result.exit_code}): {result.output.strip()}")


# ═══════════════════════════════════════════════════════════════════
# Group 1: Device discovery (no connection needed)
# ═══════════════════════════════════════════════════════════════════


def test_win32_device_list():
    """Verify --win32 flag returns windows."""
    result = runner.invoke(cli, ["device", "win32"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Win32 windows" in result.output


def test_win32_device_list_json():
    """Verify win32 --json output is parseable."""
    result = runner.invoke(cli, ["--json", "device", "win32"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert isinstance(data, dict)
    windows = data.get("win32", [])
    assert isinstance(windows, list)
    assert len(windows) > 0
    w = windows[0]
    assert "hwnd" in w
    assert "window_name" in w
    assert "class_name" in w


# ═══════════════════════════════════════════════════════════════════
# Group 2: Daemon-mode tests (default path)
# ═══════════════════════════════════════════════════════════════════


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


def test_win32_download_ocr():
    """Verify OCR model can be downloaded (or already exists)."""
    result = runner.invoke(cli, ["resource", "download-ocr"])
    _safe_print(result.output)
    assert result.exit_code == 0


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


def test_win32_swipe_json(mock_window):
    """Verify swipe --json returns structured data."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "swipe", "100,200", "100,50"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert data["action"] == "swipe"
    assert data["x1"] == 100
    assert data["y1"] == 200
    assert data["x2"] == 100
    assert data["y2"] == 50
    assert "duration" in data


def test_win32_swipe_with_elements(mock_window):
    """Verify swipe accepts Element arguments."""
    _ensure_connected(mock_window)

    # Run OCR first to populate Elements
    ocr_result = runner.invoke(cli, ["--json", "ocr"])
    if ocr_result.exit_code != 0:
        pytest.skip("OCR failed")
    data = _parse_json_output(ocr_result.output)
    if len(data.get("results", [])) < 2:
        pytest.skip("Need at least 2 OCR results for swipe test")

    # Swipe from e1 to e2
    result = runner.invoke(cli, ["swipe", "e1", "e2"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Swiped" in result.output


def test_win32_scroll(mock_window):
    """Verify scroll command executes successfully."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["scroll", "0", "-360"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Scrolled" in result.output


def test_win32_scroll_json(mock_window):
    """Verify scroll --json returns structured data."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "scroll", "0", "120"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert data["action"] == "scroll"
    assert data["dx"] == 0
    assert data["dy"] == 120


def test_win32_type(mock_window):
    """Verify type command executes successfully."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["type", "Hello"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Typed" in result.output


def test_win32_type_json(mock_window):
    """Verify type --json returns structured data."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "type", "Test123"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert data["action"] == "type"
    assert data["text"] == "Test123"


def test_win32_key_hex(mock_window):
    """Verify key command with hex code."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["key", "0x0D"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Pressed" in result.output


def test_win32_key_json(mock_window):
    """Verify key --json returns structured data."""
    _ensure_connected(mock_window)

    result = runner.invoke(cli, ["--json", "key", "tab"])
    _safe_print(result.output)
    assert result.exit_code == 0
    data = _parse_json_output(result.output)
    assert data["action"] == "key"
    assert data["keycode"] == 0x09
    assert data["keycode_hex"] == "0x09"


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


# ═══════════════════════════════════════════════════════════════════
# Group 3: Seize-mode tests (verify real interaction effects via OCR)
#
# These tests use --input-method Seize which grabs the mouse.
# They verify that clicks/keys/swipes actually trigger UI changes.
# ═══════════════════════════════════════════════════════════════════


def test_win32_click_changes_label(mock_window):
    """Verify click actually works on the mock window.

    Connects with Seize input (only method that works on tkinter),
    clicks the PRESS button, then verifies the label changes to CLICKED.
    """
    _ensure_connected_seize(mock_window)

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


def test_win32_swipe_changes_label(mock_window):
    """Verify swipe triggers the drag detection in the mock window."""
    _ensure_connected_seize(mock_window)

    # Swipe across the label area
    result = runner.invoke(cli, ["swipe", "50,100", "350,100", "--duration", "300"])
    _safe_print(result.output)
    assert result.exit_code == 0
    assert "Swiped" in result.output

    # Verify via OCR that the mock detected the swipe
    time.sleep(0.3)
    result = runner.invoke(cli, ["--json", "ocr"])
    if result.exit_code == 0:
        data = _parse_json_output(result.output)
        all_text = " ".join(r["text"] for r in data["results"])
        _safe_print(f"  OCR after swipe: {all_text}")
        assert "SWIPED" in all_text, f"Expected 'SWIPED' in OCR, got: {all_text}"


def test_win32_key_changes_label(mock_window):
    """Verify pressing a key updates the mock window label via OCR.

    The mock window binds <Key> events and changes the label to KEY:<vk>.
    """
    _ensure_connected_seize(mock_window)

    # Press F5 key
    result = runner.invoke(cli, ["key", "f5"])
    assert result.exit_code == 0

    # Wait for UI update and verify
    time.sleep(0.3)
    result = runner.invoke(cli, ["--json", "ocr"])
    if result.exit_code == 0:
        data = _parse_json_output(result.output)
        all_text = " ".join(r["text"] for r in data["results"])
        _safe_print(f"  OCR after key press: {all_text}")
        # The mock window should show KEY:<vk_code> (F5 = 0x74 = 116)
        assert "KEY" in all_text, f"Expected 'KEY:...' in OCR, got: {all_text}"


def test_win32_interaction_workflow(mock_window):
    """End-to-end interaction: type -> key -> swipe -> scroll -> ocr."""
    _ensure_connected_seize(mock_window)

    # 1. Type text
    r = runner.invoke(cli, ["type", "hello"])
    assert r.exit_code == 0, f"type failed: {r.output}"

    # 2. Press Enter
    r = runner.invoke(cli, ["key", "enter"])
    assert r.exit_code == 0, f"key failed: {r.output}"

    # 3. Swipe
    r = runner.invoke(cli, ["swipe", "50,150", "350,150"])
    assert r.exit_code == 0, f"swipe failed: {r.output}"

    # 4. Scroll
    r = runner.invoke(cli, ["scroll", "0", "-120"])
    assert r.exit_code == 0, f"scroll failed: {r.output}"

    # 5. Final OCR to verify window is still responsive
    r = runner.invoke(cli, ["--json", "ocr"])
    assert r.exit_code == 0, f"ocr failed: {r.output}"
    data = _parse_json_output(r.output)
    _safe_print(f"  Final OCR: {len(data['results'])} results")

    print("Full interaction workflow passed.")


# ═══════════════════════════════════════════════════════════════════
# Group 4: Direct-mode tests (--no-daemon, file persistence)
# ═══════════════════════════════════════════════════════════════════


def test_win32_connect_with_options(mock_window):
    """Verify --screencap-method and --input-method persist to session.json."""
    result = runner.invoke(cli, [
        "--no-daemon", "connect", "win32", mock_window["hwnd"],
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


def test_win32_session_persistence(mock_window):
    """Verify session is saved to disk and can be reloaded."""
    _ensure_connected_direct(mock_window)

    from maafw_cli.core.session import load_session

    session = load_session()
    assert session is not None
    assert session.type == "win32"
    assert session.window_name != ""
    assert session.address.startswith("0x")
    assert session.screencap_methods != 0
    assert session.input_methods != 0


def test_win32_reconnect(mock_window):
    """Verify reconnection works via session file (--no-daemon)."""
    _ensure_connected_direct(mock_window)

    result = runner.invoke(cli, ["--no-daemon", "-v", "screenshot"])
    _safe_print(result.output)
    assert result.exit_code == 0
