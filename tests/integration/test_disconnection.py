"""
Integration test: device disconnection detection.

Verifies that when a Win32 window is closed, the session correctly
reports disconnected status and operations raise DeviceConnectionError.

    uv run pytest tests/integration/test_disconnection.py -m integration -v -s
"""
from __future__ import annotations

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
]

runner = CliRunner(charset="utf-8")

_MOCK_SCRIPT = str(Path(__file__).parent.parent / "mock_win32_window.py")


def _ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


@pytest.fixture(scope="module")
def disconnection_window():
    """Launch a mock window, connect, yield info, then close window (not session).

    The test will verify behaviour AFTER the window is closed but the
    daemon session still exists.
    """
    token = uuid.uuid4().hex[:8]
    expected_title = f"MaafwTest_{token}"
    session_name = f"disconnect_{token}"

    proc = subprocess.Popen(
        [sys.executable, _MOCK_SCRIPT, token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[{_ts()}] Launched mock window (pid={proc.pid}, title={expected_title})")
    time.sleep(1.5)

    # Find window
    window = None
    for attempt in range(5):
        result = runner.invoke(cli, ["--json", "device", "win32"])
        if result.exit_code == 0:
            import json
            try:
                data = json.loads(result.output)
            except (json.JSONDecodeError, ValueError):
                pass
            else:
                windows = data.get("win32", data) if isinstance(data, dict) else data
                for w in windows:
                    if expected_title in w.get("window_name", ""):
                        window = w
                        break
        if window:
            break
        time.sleep(0.5)

    if window is None:
        proc.kill()
        proc.wait(timeout=5)
        pytest.skip(f"Could not find window '{expected_title}'")

    # Connect
    cmd = ["--on", session_name, "connect", "win32", window["hwnd"]]
    print(f"[{_ts()}] Connecting: {' '.join(cmd)}")
    result = runner.invoke(cli, cmd)
    if result.exit_code != 0:
        proc.kill()
        proc.wait(timeout=5)
        pytest.fail(f"Failed to connect: {result.output}")
    print(f"[{_ts()}] Connected to session '{session_name}'")

    yield {
        "session_name": session_name,
        "window": window,
        "proc": proc,
    }

    # Teardown: close session, kill process if still alive
    runner.invoke(cli, ["session", "close", session_name])
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)
    runner.invoke(cli, ["daemon", "stop"])
    print(f"[{_ts()}] Teardown complete")


class TestDisconnectionDetection:
    """Verify device disconnection is detected after window close."""

    def test_connected_before_close(self, disconnection_window):
        """Session reports connected while window is alive."""
        info = disconnection_window
        session_name = info["session_name"]

        result = runner.invoke(cli, ["--json", "session", "list"])
        assert result.exit_code == 0

        import json
        data = json.loads(result.output)
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        by_name = {s["name"]: s for s in sessions}
        assert session_name in by_name
        assert by_name[session_name]["connected"] is True

    def test_disconnected_after_close(self, disconnection_window):
        """After killing the window, session reports disconnected."""
        info = disconnection_window
        session_name = info["session_name"]
        proc = info["proc"]

        # Kill the window
        print(f"[{_ts()}] Killing mock window process...")
        proc.kill()
        proc.wait(timeout=5)
        time.sleep(1)  # Give OS time to clean up window handle

        result = runner.invoke(cli, ["--json", "session", "list"])
        assert result.exit_code == 0

        import json
        data = json.loads(result.output)
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        by_name = {s["name"]: s for s in sessions}
        assert session_name in by_name
        assert by_name[session_name]["connected"] is False

    def test_operation_after_disconnect_errors(self, disconnection_window):
        """Operations on a disconnected session should return an error."""
        info = disconnection_window
        session_name = info["session_name"]

        # Window should already be dead from previous test
        result = runner.invoke(cli, ["--on", session_name, "ocr"])
        # Should fail with exit code 3 (DeviceConnectionError)
        assert result.exit_code == 3
        assert "disconnected" in result.output.lower()
