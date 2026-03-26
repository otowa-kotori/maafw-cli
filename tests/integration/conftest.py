"""
Shared fixtures and helpers for integration tests.

Three mock windows:
- ``mock_window`` — READY/PRESS/Entry for OCR + interaction tests
- ``reco_window`` — fixture icons for TemplateMatch/FeatureMatch/ColorMatch
- ``pipeline_window`` — multi-stage app for pipeline automation tests

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
from datetime import datetime
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
_PIPELINE_SCRIPT = str(_TESTS_DIR / "mock_pipeline_window.py")
_FIXTURES_DIR = _TESTS_DIR / "fixtures"
_PIPELINE_FIXTURES_DIR = _FIXTURES_DIR / "pipeline"


def _ts() -> str:
    """Current timestamp string for logging."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


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


# ── subprocess tracking ────────────────────────────────────────

_child_procs: list[subprocess.Popen] = []

# ── connection state ───────────────────────────────────────────

_connected_sessions: set[str] = set()
_fixture_errors: dict[str, str] = {}  # fixture name → error message
_fixture_failed_once: set[str] = set()  # fixtures that already caused one FAIL


def ensure_connected(
    win: dict,
    session_name: str | None = None,
    input_method: str | None = None,
) -> None:
    """Connect to a window via daemon. Caches by session name."""
    key = session_name or win["hwnd"]
    if key in _connected_sessions:
        return
    cmd = ["connect", "win32", win["hwnd"]]
    if session_name:
        cmd += ["--as", session_name]
    if input_method:
        cmd += ["--input-method", input_method]
    print(f"[{_ts()}] Connecting: {' '.join(cmd)}")
    result = runner.invoke(cli, cmd)
    if result.exit_code != 0:
        raise RuntimeError(
            f"[{_ts()}] Failed to connect (exit {result.exit_code}): "
            f"{result.output.strip()}"
        )
    print(f"[{_ts()}] Connected: {key}")
    _connected_sessions.add(key)


# ── helper: launch a mock window ─────────────────────────────


def _launch_window(script: str, title_prefix: str):
    """Launch a mock window subprocess and find it via device list.

    Returns ``(window_info_dict, subprocess.Popen)``.
    """
    token = uuid.uuid4().hex[:8]
    expected_title = f"{title_prefix}_{token}"

    print(f"[{_ts()}] Launching {script} (expecting '{expected_title}')")
    proc = subprocess.Popen(
        [sys.executable, script, token],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _child_procs.append(proc)
    print(f"[{_ts()}] Process started: pid={proc.pid}")
    time.sleep(1.5)

    window = None
    for attempt in range(5):
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

    print(f"[{_ts()}] Found window: hwnd={window['hwnd']} title={window['window_name']}")
    return window, proc


# ── session-scoped mock window (OCR / interaction) ────────────


@pytest.fixture(scope="session")
def mock_window():
    """Launch the READY/PRESS mock window."""
    window, proc = _launch_window(_MOCK_SCRIPT, "MaafwTest")
    yield window


# ── session-scoped reco window (TemplateMatch / FeatureMatch) ──


@pytest.fixture(scope="session")
def reco_window():
    """Launch the reco mock window with fixture icons.

    Also loads fixture images into daemon's Resource and connects.
    On failure, records error for deferred fail/skip instead of crashing the fixture.
    """
    window, proc = _launch_window(_RECO_SCRIPT, "MaafwReco")

    try:
        ensure_connected(window, session_name="reco")
    except RuntimeError as e:
        _fixture_errors["reco_window"] = str(e)
        yield window
        return

    # Load fixture images into daemon's Resource
    r = runner.invoke(cli, ["resource", "load-image", str(_FIXTURES_DIR)])
    if r.exit_code != 0:
        _fixture_errors["reco_window"] = f"resource load-image failed: {r.output}"

    yield window


# ── session-scoped pipeline window (multi-stage app) ──────────


@pytest.fixture(scope="session")
def pipeline_window():
    """Launch the multi-stage pipeline mock window.

    Connects with Seize input (required for button clicks in tkinter)
    and loads the pipeline fixture JSON into the daemon's Resource.
    On failure, records error for deferred fail/skip.
    """
    window, proc = _launch_window(_PIPELINE_SCRIPT, "MaafwPipeline")

    try:
        ensure_connected(window, session_name="pipeline", input_method="Seize")
    except RuntimeError as e:
        _fixture_errors["pipeline_window"] = str(e)
        yield window
        return

    # Load pipeline JSON into daemon's Resource
    r = runner.invoke(cli, [
        "--on", "pipeline", "pipeline", "load", str(_PIPELINE_FIXTURES_DIR),
    ])
    if r.exit_code != 0:
        _fixture_errors["pipeline_window"] = f"pipeline load failed: {r.output}"

    yield window


@pytest.fixture(autouse=True)
def _check_fixture_health(request):
    """Before each test, check if its fixtures had setup errors.

    First test using a broken fixture → FAIL. Subsequent tests → SKIP.
    """
    for fixture_name, error_msg in _fixture_errors.items():
        if fixture_name in request.fixturenames:
            if fixture_name not in _fixture_failed_once:
                _fixture_failed_once.add(fixture_name)
                pytest.fail(f"{fixture_name} setup failed: {error_msg}")
            else:
                pytest.skip(f"{fixture_name} setup failed (see earlier FAIL)")


# ── teardown ─────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _cleanup():
    """Stop daemon, kill mock windows, and clean up after all tests."""
    yield
    # Stop daemon
    runner.invoke(cli, ["daemon", "stop"])
    # Kill all mock window processes
    for proc in _child_procs:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    _child_procs.clear()
    # Clean up screenshot files
    for f in glob.glob("screenshot_*.png"):
        try:
            Path(f).unlink()
        except OSError:
            pass
