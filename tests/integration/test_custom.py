"""
Integration tests for Custom Recognition & Custom Action.

Tests:
- custom load/list/unload/clear CLI commands
- Custom nodes in pipeline execution (mixed with builtin nodes)

Uses the pipeline mock window (Welcome -> Login -> Home flow).

    uv run pytest tests/integration/test_custom.py -m integration -v -s
"""
from __future__ import annotations

from pathlib import Path

import pytest

from maafw_cli.cli import cli
from .conftest import (
    _launch_window,
    _PIPELINE_SCRIPT,
    _FIXTURES_DIR,
    _PIPELINE_FIXTURES_DIR,
    _teardown_fixture,
    ensure_connected,
    invoke_on,
    parse_json_output,
    runner,
    safe_print,
)

_TESTS_DIR = Path(__file__).parent.parent
_CUSTOM_SCRIPT = str(_TESTS_DIR / "mock_custom_callbacks.py")
_CUSTOM_PIPELINE_DIR = str(_PIPELINE_FIXTURES_DIR)


# ── fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def custom_window():
    """Launch the pipeline mock window for custom callback tests.

    Connects with Seize input, loads the custom callback script,
    and loads the pipeline JSON including custom_flow.json.
    """
    window, proc = _launch_window(_PIPELINE_SCRIPT, "MaafwPipeline")

    try:
        ensure_connected(
            window, session_name="custom",
            input_method="Seize",
        )
    except RuntimeError as e:
        proc.kill()
        proc.wait(timeout=5)
        pytest.skip(f"Could not connect: {e}")

    # Load custom callbacks
    r = invoke_on("custom", ["custom", "load", _CUSTOM_SCRIPT])
    if r.exit_code != 0:
        safe_print(f"custom load failed: {r.output}")
        proc.kill()
        proc.wait(timeout=5)
        pytest.skip(f"custom load failed: {r.output}")

    # Load pipeline JSON (includes custom_flow.json)
    r = invoke_on("custom", ["pipeline", "load", _CUSTOM_PIPELINE_DIR])
    if r.exit_code != 0:
        safe_print(f"pipeline load failed: {r.output}")
        proc.kill()
        proc.wait(timeout=5)
        pytest.skip(f"pipeline load failed: {r.output}")

    yield window

    _teardown_fixture("custom", proc)


# ═══════════════════════════════════════════════════════════════════
# Test Group 1: CLI commands
# ═══════════════════════════════════════════════════════════════════


class TestCustomLoad:
    """Test custom load/list/unload/clear CLI commands."""

    def test_load_json(self, custom_window):
        """custom load returns recognitions/actions lists."""
        r = invoke_on("custom", ["--json", "custom", "load", _CUSTOM_SCRIPT, "--reload"])
        safe_print(r.output)
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        assert "FindTextCustom" in data["recognitions"]
        assert "ClickTargetCustom" in data["actions"]
        assert "InputTextCustom" in data["actions"]

    def test_list_json(self, custom_window):
        """custom list shows registered callbacks."""
        r = invoke_on("custom", ["--json", "custom", "list"])
        safe_print(r.output)
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        assert "FindTextCustom" in data["recognitions"]
        assert "ClickTargetCustom" in data["actions"]
        assert "InputTextCustom" in data["actions"]

    def test_unload_and_relist(self, custom_window):
        """Unload a recognition, verify it's gone, then reload."""
        # Unload
        r = invoke_on("custom", ["--json", "custom", "unload", "FindTextCustom", "--type", "recognition"])
        safe_print(r.output)
        assert r.exit_code == 0

        # List — should be missing
        r = invoke_on("custom", ["--json", "custom", "list"])
        data = parse_json_output(r.output)
        assert "FindTextCustom" not in data["recognitions"]
        assert "ClickTargetCustom" in data["actions"]  # action still there

        # Reload
        r = invoke_on("custom", ["custom", "load", _CUSTOM_SCRIPT, "--reload"])
        assert r.exit_code == 0

    def test_clear_all(self, custom_window):
        """Clear all, verify empty, then reload."""
        r = invoke_on("custom", ["--json", "custom", "clear"])
        safe_print(r.output)
        assert r.exit_code == 0

        r = invoke_on("custom", ["--json", "custom", "list"])
        data = parse_json_output(r.output)
        assert data["recognitions"] == []
        assert data["actions"] == []

        # Reload for subsequent tests
        r = invoke_on("custom", ["custom", "load", _CUSTOM_SCRIPT, "--reload"])
        assert r.exit_code == 0


# ═══════════════════════════════════════════════════════════════════
# Test Group 2: direct reco Custom command
# ═══════════════════════════════════════════════════════════════════


class TestCustomRecoCommand:
    """Direct ``reco Custom`` command should support custom params."""

    def test_reco_custom_with_kv_json_param(self, custom_window):
        r = invoke_on("custom", [
            "--json", "reco", "Custom",
            "custom_recognition=FindTextCustom",
            'custom_recognition_param={"expected": "START"}',
        ])
        safe_print(r.output)
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        assert data["reco_type"] == "Custom"
        assert len(data["results"]) >= 1
        assert "ref" in data["results"][0]
        assert "box" in data["results"][0]

    def test_reco_custom_with_raw_json_param(self, custom_window):
        r = invoke_on("custom", [
            "--json", "reco",
            "--raw",
            '{"recognition":"Custom","custom_recognition":"FindTextCustom","custom_recognition_param":{"expected":"START"}}',
        ])
        safe_print(r.output)
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        assert data["reco_type"] == "Custom"
        assert len(data["results"]) >= 1


# ═══════════════════════════════════════════════════════════════════
# Test Group 3: Pipeline execution with Custom nodes
# ═══════════════════════════════════════════════════════════════════


class TestCustomPipelineRun:
    """Execute a pipeline mixing Custom and builtin nodes."""

    def test_run_custom_pipeline(self, custom_window):
        """End-to-end: custom callbacks drive mock window state transitions."""
        r = runner.invoke(cli, [
            "--json", "--on", "custom",
            "pipeline", "run", _CUSTOM_PIPELINE_DIR, "CustomClickStart",
        ])
        safe_print(r.output)
        assert r.exit_code == 0, f"Pipeline failed: {r.output}"

        data = parse_json_output(r.output)

        # Basic structure
        assert data["status"] == "succeeded"
        assert data["entry"] == "CustomClickStart"

        # All 8 nodes completed
        node_names = [n["name"] for n in data["nodes"]]
        assert len(node_names) == 8, f"Expected 8 nodes, got {len(node_names)}: {node_names}"

        expected_order = [
            "CustomClickStart",
            "CustomVerifyLogin",
            "FocusUsername_C",
            "TypeUsername_C",
            "FocusPassword_C",
            "TypePassword_C",
            "CustomClickSubmit",
            "CustomVerifyHome",
        ]
        assert node_names == expected_order

        for node in data["nodes"]:
            assert node["completed"], f"Node '{node['name']}' not completed"

        # Custom nodes should have Custom recognition algorithm
        custom_reco_nodes = {
            "CustomClickStart", "CustomVerifyLogin",
            "CustomClickSubmit", "CustomVerifyHome",
        }
        for node in data["nodes"]:
            if node["name"] in custom_reco_nodes:
                assert "Custom" in node["recognition"]["algorithm"], (
                    f"Node '{node['name']}' expected Custom recognition"
                )
                assert node["recognition"]["hit"] is True

        # TypeUsername_C should use Custom action (InputTextCustom via custom_action_param)
        type_username = next(n for n in data["nodes"] if n["name"] == "TypeUsername_C")
        assert type_username["action"]["type"] == "Custom"
        assert type_username["action"]["success"] is True
