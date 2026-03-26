"""
Integration tests for the ``pipeline`` command.

Tests pipeline operations against a real mock window:
- ``pipeline load`` — loads pipeline JSON into Resource
- ``pipeline list`` — lists loaded node names
- ``pipeline show`` — displays node definitions
- ``pipeline validate`` — validates pipeline JSON
- ``pipeline run`` — executes a multi-step automation pipeline

The mock pipeline window (``mock_pipeline_window.py``) is a multi-stage
tkinter app that simulates: Welcome → Login → Home → Settings → Complete.

    uv run pytest tests/integration/test_pipeline.py -v -s
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from maafw_cli.cli import cli
from .conftest import (
    ensure_connected,
    parse_json_output,
    runner,
    safe_print,
    _PIPELINE_FIXTURES_DIR,
)


_PIPELINE_DIR = str(_PIPELINE_FIXTURES_DIR)

_ALL_EXPECTED_NODES = {
    "ClickStart", "FocusUsername", "TypeUsername",
    "FocusPassword", "TypePassword", "ClickSubmit",
    "VerifyHome", "ClickSettings", "VerifySettings",
    "ClickBack", "ClickLogout", "VerifyComplete",
}


# ═══════════════════════════════════════════════════════════════════
# Group 1: Pipeline resource operations (load, list, show, validate)
# ═══════════════════════════════════════════════════════════════════


class TestPipelineLoad:
    """Test loading pipeline JSON into the Resource."""

    def test_load_human(self, pipeline_window):
        """pipeline load should report success in human mode."""
        result = runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        assert "Loaded" in result.output
        assert "nodes" in result.output.lower()

    def test_load_json(self, pipeline_window):
        """pipeline load --json should return structured data."""
        result = runner.invoke(cli, [
            "--json", "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["loaded"] is True
        assert data["node_count"] == 12
        assert isinstance(data["nodes"], list)


class TestPipelineList:
    """Test listing loaded pipeline nodes."""

    def test_list_human(self, pipeline_window):
        """pipeline list should show node names."""
        runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        result = runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "list",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        assert "ClickStart" in result.output

    def test_list_json(self, pipeline_window):
        """pipeline list --json should return all node names."""
        runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        result = runner.invoke(cli, [
            "--json", "--on", "pipeline", "pipeline", "list",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        loaded_nodes = set(data["nodes"])
        assert _ALL_EXPECTED_NODES.issubset(loaded_nodes), (
            f"Missing nodes: {_ALL_EXPECTED_NODES - loaded_nodes}"
        )


class TestPipelineShow:
    """Test showing individual node definitions."""

    def test_show_human(self, pipeline_window):
        """pipeline show should display node JSON."""
        runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        result = runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "show", "ClickStart",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        assert "ClickStart" in result.output

    def test_show_json(self, pipeline_window):
        """pipeline show --json should return full node definition."""
        runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        result = runner.invoke(cli, [
            "--json", "--on", "pipeline", "pipeline", "show", "ClickStart",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["node"] == "ClickStart"
        assert isinstance(data["definition"], dict)

    def test_show_nonexistent(self, pipeline_window):
        """pipeline show for missing node should error."""
        runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "load", _PIPELINE_DIR,
        ])
        result = runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "show", "NonExistentNode",
        ])
        safe_print(result.output)
        assert result.exit_code != 0


class TestPipelineValidate:
    """Test pipeline validation."""

    def test_validate_valid(self, pipeline_window):
        """pipeline validate should succeed on valid pipeline JSON."""
        result = runner.invoke(cli, [
            "--on", "pipeline", "pipeline", "validate", _PIPELINE_DIR,
        ])
        safe_print(result.output)
        assert result.exit_code == 0

    def test_validate_valid_json(self, pipeline_window):
        """pipeline validate --json should return valid=True."""
        result = runner.invoke(cli, [
            "--json", "--on", "pipeline", "pipeline", "validate", _PIPELINE_DIR,
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["valid"] is True
        assert data["node_count"] > 0


# ═══════════════════════════════════════════════════════════════════
# Group 2: Pipeline execution (run)
#
# The mock window starts on the Welcome screen. The pipeline automates:
# Welcome → Login (type user/pass) → Home → Settings → Back → Logout → Complete
# ═══════════════════════════════════════════════════════════════════


class TestPipelineRun:
    """Test executing pipeline against the mock pipeline window.

    NOTE: The full pipeline run mutates the window state (Welcome → Complete),
    so only one test can run the full pipeline per window instance.
    We run the full pipeline once in JSON mode and verify everything.
    """

    def test_run_full_pipeline(self, pipeline_window):
        """Run the complete 12-node pipeline and verify all nodes succeed."""
        result = runner.invoke(cli, [
            "--json", "--on", "pipeline",
            "pipeline", "run", _PIPELINE_DIR, "ClickStart",
        ])
        safe_print(result.output)
        assert result.exit_code == 0, f"Pipeline run failed: {result.output}"

        data = parse_json_output(result.output)
        assert data["entry"] == "ClickStart"
        assert data["status"] == "succeeded"
        assert data["node_count"] == 12, (
            f"Expected 12 nodes, got {data['node_count']}. "
            f"Nodes: {[n.get('name') for n in data.get('nodes', [])]}"
        )
        assert data["elapsed_ms"] > 0

        # Verify all 12 nodes completed
        for node in data["nodes"]:
            assert node["completed"], (
                f"Node '{node.get('name')}' not completed"
            )

        # Verify key nodes are present in order
        node_names = [n["name"] for n in data["nodes"]]
        assert node_names[0] == "ClickStart"
        assert node_names[-1] == "VerifyComplete"
        assert "ClickSubmit" in node_names
        assert "VerifyHome" in node_names
        assert "ClickSettings" in node_names

        # Verify recognition details on first node
        first = data["nodes"][0]
        assert first["recognition"]["algorithm"] == "OCR"
        assert first["recognition"]["hit"] is True
        assert first["recognition"]["text"] == "START"
        assert first["action"]["type"] == "Click"
        assert first["action"]["success"] is True
