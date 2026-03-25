"""
Shared fixtures and helpers for integration tests.

Two mock windows:
- ``mock_window`` — READY/PRESS/Entry for OCR + interaction tests
- ``reco_window`` — fixture icons for TemplateMatch/FeatureMatch/ColorMatch

Usage:
    uv run pytest tests/integration/ -v -s
"""
from __future__ import annotations

import glob
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from maafw_cli.cli import cli

# ── skip on non-Windows ────────────────────────────────────────


def pytest_collection_modifyitems(items):
    """Auto-skip on non-Windows + mark all as 'integration'."""
    integration_mark = pytest.mark.integration
    skip_mark = pytest.mark.skip(reason="Integration tests require Windows")
    for item in items:
        item.add_marker(integration_mark)
        if sys.platform != "win32":
            item.add_marker(skip_mark)


# ── shared runner ──────────────────────────────────────────────

runner = CliRunner(charset="utf-8")

_TESTS_DIR = Path(__file__).parent.parent
_MOCK_SCRIPT = str(_TESTS_DIR / "mock_win32_window.py")
_RECO_SCRIPT = str(_TESTS_DIR / "mock_reco_window.py")
_FIXTURES_DIR = _TESTS_DIR / "fixtures"


# ── helpers (importable by test modules) ───────────────────────


def parse_json_output(output: str):
    """Extract JSON from CliRunner output that may have logger lines mixed in."""
    i = 0
    while i < len(output):
        ch = output[i]
        if ch in ("[", "{"):
            try:
                return json.loads(output[i:])
            except json.JSONDecodeError:
                pass
        i += 1
    raise ValueError(f"No JSON found in output: {output[:200]}")


def safe_print(text: str) -> None:
    """Print text safely on terminals that don't support full Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


# ── connection state ───────────────────────────────────────────

_connected_sessions: set[str] = set()


def ensure_connected(win: dict, session_name: str | None = None) -> None:
    """Connect to a window via daemon. Caches by session name."""
    key = session_name or win["hwnd"]
    if key in _connected_sessions:
        return
    cmd = ["connect", "win32", win["hwnd"]]
    if session_name:
        cmd += ["--as", session_name]
    result = runner.invoke(cli, cmd)
    if result.exit_code != 0:
        lines = [f"Failed to connect (exit {result.exit_code}): {result.output.strip()}"]
        dev = runner.invoke(cli, ["--json", "device", "win32"])
        lines.append(f"device win32: {dev.output.strip()}")
        pytest.fail("\n".join(lines))
    _connected_sessions.add(key)


# ── helper: launch a mock window ─────────────────────────────


def _launch_window(script: str, title_prefix: str):
    """Launch a mock window subprocess and find it via device list.

    Returns ``(window_info_dict, subprocess.Popen)``.
    """
    token = uuid.uuid4().hex[:8]
    expected_title = f"{title_prefix}_{token}"

    proc = subprocess.Popen(
        [sys.executable, script, token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    window = None
    for _attempt in range(5):
        result = runner.invoke(cli, ["--json", "device", "win32"])
        if result.exit_code != 0:
            time.sleep(0.5)
            continue
        try:
            data = parse_json_output(result.output)
        except ValueError:
            time.sleep(0.5)
            continue
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
        pytest.skip(f"Could not find window '{expected_title}' after launch")

    return window, proc


# ── session-scoped mock window (OCR / interaction) ────────────


@pytest.fixture(scope="session")
def mock_window():
    """Launch the READY/PRESS mock window."""
    window, proc = _launch_window(_MOCK_SCRIPT, "MaafwTest")
    yield window
    proc.kill()
    proc.wait()


# ── session-scoped reco window (TemplateMatch / FeatureMatch) ──


@pytest.fixture(scope="session")
def reco_window():
    """Launch the reco mock window with fixture icons.

    Also loads fixture images into daemon's Resource and connects.
    """
    window, proc = _launch_window(_RECO_SCRIPT, "MaafwReco")

    # Connect
    ensure_connected(window, session_name="reco")

    # Load fixture images into daemon's Resource
    r = runner.invoke(cli, ["resource", "load-image", str(_FIXTURES_DIR)])
    if r.exit_code != 0:
        proc.kill()
        pytest.skip(f"resource load-image failed: {r.output}")

    yield window

    proc.kill()
    proc.wait()


# ── teardown ─────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _cleanup():
    """Stop daemon and clean up screenshot files after all tests."""
    yield
    runner.invoke(cli, ["daemon", "stop"])
    for f in glob.glob("screenshot_*.png"):
        try:
            Path(f).unlink()
        except OSError:
            pass
