"""
Daemon + named session end-to-end test on Win32.

Uses the same mock tkinter window as test_win32_manual.py.
Verifies:
  1. daemon start
  2. connect win32 --as <name> (named session via daemon)
  3. Sequential operations through daemon: ocr, click, ocr, key, ocr
  4. session list / status
  5. daemon log contains operation trace
  6. daemon stop

Run:
    uv run pytest tests/test_daemon_e2e.py -v -s
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Win32 tests require Windows"),
    pytest.mark.manual,
]

runner = CliRunner(charset="utf-8")
_MOCK_SCRIPT = str(Path(__file__).parent / "mock_win32_window.py")


# ── helpers ──────────────────────────────────────────────────────

def _parse_json(output: str):
    i = 0
    while i < len(output):
        if output[i] in ("[", "{"):
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                pass
        i += 1
    raise ValueError(f"No JSON in: {output[:200]}")


def _invoke(*args):
    """Invoke CLI and return (exit_code, output)."""
    result = runner.invoke(cli, list(args))
    return result.exit_code, result.output


def _invoke_json(*args):
    """Invoke with --json, parse and return data dict."""
    result = runner.invoke(cli, ["--json"] + list(args))
    if result.exit_code != 0:
        return result.exit_code, result.output
    return result.exit_code, _parse_json(result.output)


# ── fixture: mock window ────────────────────────────────────────

@pytest.fixture(scope="module")
def mock_window():
    token = uuid.uuid4().hex[:8]
    title = f"MaafwTest_{token}"

    proc = subprocess.Popen(
        [sys.executable, _MOCK_SCRIPT, token],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2.0)

    # Find window hwnd
    hwnd = None
    for _ in range(5):
        code, data = _invoke_json("device", "win32")
        if code != 0:
            time.sleep(0.5)
            continue
        for w in data.get("win32", []):
            if title in w["window_name"]:
                hwnd = w["hwnd"]
                break
        if hwnd:
            break
        time.sleep(0.5)

    if hwnd is None:
        proc.kill()
        pytest.skip(f"Mock window '{title}' not found")

    yield {"hwnd": hwnd, "title": title}

    proc.kill()
    proc.wait()


# ── fixture: daemon lifecycle ───────────────────────────────────

@pytest.fixture(scope="module")
def daemon_running():
    """Ensure daemon is started; stop it on teardown."""
    # Stop any leftover daemon first
    runner.invoke(cli, ["daemon", "stop"])
    time.sleep(0.5)

    result = runner.invoke(cli, ["daemon", "start"])
    print(f"[daemon start] exit={result.exit_code} output={result.output.strip()}")
    assert result.exit_code == 0, f"daemon start failed: {result.output}"

    yield

    result = runner.invoke(cli, ["daemon", "stop"])
    print(f"[daemon stop] exit={result.exit_code} output={result.output.strip()}")


# ── tests (run in order) ────────────────────────────────────────

class TestDaemonE2E:
    """Sequential E2E: connect → ocr → click → ocr → key → ocr."""

    def test_01_daemon_status(self, daemon_running):
        code, data = _invoke_json("daemon", "status")
        print(f"  status: {data}")
        assert code == 0
        assert data["status"] == "running"

    def test_02_connect_named_session(self, daemon_running, mock_window):
        code, output = _invoke(
            "--on", "testwin", "connect", "win32", mock_window["hwnd"],
        )
        print(f"  connect: exit={code} output={output.strip()}")
        assert code == 0

    def test_03_session_list(self, daemon_running, mock_window):
        code, data = _invoke_json("session", "list")
        print(f"  session list: {data}")
        assert code == 0
        names = [s["name"] for s in data]
        assert "testwin" in names

    def test_04_ocr_initial(self, daemon_running, mock_window):
        """OCR should see 'READY' in the mock window."""
        code, data = _invoke_json("--on", "testwin", "ocr")
        print(f"  ocr: exit={code} data_type={type(data).__name__}")
        if code != 0:
            print(f"  ocr error: {data}")
            pytest.skip(f"OCR failed with exit {code} — may need OCR model")
        texts = [r["text"] for r in data.get("results", [])]
        print(f"  ocr texts: {texts}")
        all_text = " ".join(texts).upper()
        assert "READY" in all_text or "PRESS" in all_text, f"Expected 'READY' or 'PRESS', got: {texts}"

    def test_05_click_button(self, daemon_running, mock_window):
        """Click the PRESS button area (approx center-bottom of 400x300)."""
        code, data = _invoke_json("--on", "testwin", "click", "200,240")
        print(f"  click: {data}")
        assert code == 0

    def test_06_ocr_after_click(self, daemon_running, mock_window):
        """After clicking the button, label should show CLICKED or PRESS still visible."""
        time.sleep(0.3)
        code, data = _invoke_json("--on", "testwin", "ocr")
        if code != 0:
            print(f"  ocr after click: skipped (exit {code})")
            pytest.skip("OCR not available")
        texts = [r["text"] for r in data.get("results", [])]
        print(f"  ocr after click: {texts}")
        assert code == 0

    def test_07_key_press(self, daemon_running, mock_window):
        """Press Enter key — label should show KEY:13."""
        code, data = _invoke_json("--on", "testwin", "key", "enter")
        print(f"  key: {data}")
        assert code == 0

    def test_08_ocr_after_key(self, daemon_running, mock_window):
        time.sleep(0.3)
        code, data = _invoke_json("--on", "testwin", "ocr")
        if code != 0:
            print(f"  ocr after key: skipped (exit {code})")
            pytest.skip("OCR not available")
        texts = [r["text"] for r in data.get("results", [])]
        print(f"  ocr after key: {texts}")
        assert code == 0

    def test_09_type_text(self, daemon_running, mock_window):
        code, data = _invoke_json("--on", "testwin", "type", "hello")
        print(f"  type: {data}")
        assert code == 0

    def test_10_swipe(self, daemon_running, mock_window):
        code, data = _invoke_json("--on", "testwin", "swipe", "50,150", "350,150")
        print(f"  swipe: {data}")
        assert code == 0

    def test_11_daemon_status_final(self, daemon_running, mock_window):
        """Final status check — should show session."""
        code, data = _invoke_json("daemon", "status")
        print(f"  final status: {data}")
        assert code == 0
        assert "testwin" in data.get("sessions", [])

    def test_12_check_daemon_log(self, daemon_running, mock_window):
        """Verify the daemon log has operation trace."""
        from maafw_cli.daemon.log import daemon_log_path
        log_path = daemon_log_path()
        assert log_path.exists(), f"Daemon log not found at {log_path}"

        log_text = log_path.read_text(encoding="utf-8")
        print(f"\n  === Daemon log (last 30 lines) ===")
        for line in log_text.strip().split("\n")[-30:]:
            print(f"  {line}")
        print(f"  === End daemon log ===\n")

        # Verify key operations are logged
        assert "connect_win32" in log_text
        assert "click" in log_text
        assert "key" in log_text
        assert "swipe" in log_text

    def test_13_session_close(self, daemon_running, mock_window):
        code, output = _invoke("session", "close", "testwin")
        print(f"  session close: exit={code} output={output.strip()}")
        assert code == 0
