"""
Integration test: full clicking game pipeline run.

Launches a fresh game window and runs the complete pipeline end-to-end.
Separate module from test_clicking_game.py so each module has only one
game window (module-scoped fixture teardown).

    uv run pytest tests/integration/test_game_pipeline_run.py -m integration -v -s
"""
from __future__ import annotations

import re

import pytest

from maafw_cli.cli import cli
from .conftest import (
    _launch_window,
    _GAME_SCRIPT,
    _FIXTURES_DIR,
    _PIPELINE_FIXTURES_DIR,
    _teardown_fixture,
    ensure_connected,
    parse_json_output,
    runner,
    safe_print,
)

_GAME_PIPELINE_DIR = str(_PIPELINE_FIXTURES_DIR)


class TestGamePipelineRun:
    """Execute the clicking game pipeline end-to-end on a fresh window."""

    def test_run_clicking_game_pipeline(self):
        """Run the full clicking game pipeline and verify results."""
        # Launch a fresh game window
        window, proc = _launch_window(_GAME_SCRIPT, "MaafwGame")
        try:
            ensure_connected(
                window, session_name="game_run",
                input_method="Seize", screencap_method="FramePool",
            )
        except RuntimeError as e:
            proc.kill()
            pytest.skip(f"Could not connect: {e}")

        r = runner.invoke(cli, [
            "--on", "game_run", "resource", "load-image", str(_FIXTURES_DIR),
        ])
        if r.exit_code != 0:
            proc.kill()
            pytest.skip(f"resource load-image failed: {r.output}")

        r = runner.invoke(cli, [
            "--on", "game_run", "pipeline", "load", str(_PIPELINE_FIXTURES_DIR),
        ])
        if r.exit_code != 0:
            proc.kill()
            pytest.skip(f"pipeline load failed: {r.output}")

        try:
            # Run the pipeline
            result = runner.invoke(cli, [
                "--json", "--on", "game_run",
                "pipeline", "run", _GAME_PIPELINE_DIR, "ClickPlay",
            ])
            safe_print(result.output)
            assert result.exit_code == 0, f"Pipeline failed: {result.output}"

            data = parse_json_output(result.output)

            # ── Basic structure ──
            assert data["entry"] == "ClickPlay"
            assert data["status"] == "succeeded"

            # ── Node traversal ──
            node_names = [n["name"] for n in data["nodes"]]
            assert node_names[0] == "ClickPlay"
            assert node_names[-1] == "ReadScore"
            assert "GameOver_Detect" in node_names
            assert "WaitGameScreen" in node_names

            # ── Loop verification ──
            click_nodes = [n for n in node_names if n.startswith("Click_")]
            assert len(click_nodes) >= 1, f"Should click at least once: {click_nodes}"

            loop_count = node_names.count("GameLoop")
            assert loop_count >= 2, f"Should loop at least twice: {loop_count}"

            cursor_resets = node_names.count("CursorReset")
            assert cursor_resets == len(click_nodes), (
                f"CursorReset ({cursor_resets}) should match clicks ({len(click_nodes)})"
            )

            # ── All nodes completed ──
            for node in data["nodes"]:
                assert node["completed"], f"Node '{node['name']}' not completed"

            # ── Score extraction ──
            read_score_node = data["nodes"][-1]
            assert read_score_node["name"] == "ReadScore"
            score_text = read_score_node["recognition"].get("text", "")
            m = re.search(r"Score:\s*(\d+)", score_text)
            assert m, f"Could not extract score: {score_text}"
            score_value = int(m.group(1))
            safe_print(f"  Pipeline score: {score_value}")
            assert score_value >= 3, f"Score too low: {score_value}"

            # ── Read misses from game over screen ──
            r = runner.invoke(cli, ["--on", "game_run", "--json", "reco", "OCR"])
            if r.exit_code == 0:
                ocr_data = parse_json_output(r.output)
                all_text = " ".join(x["text"] for x in ocr_data["results"])
                m = re.search(r"Misses:\s*(\d+)", all_text)
                if m:
                    misses = int(m.group(1))
                    safe_print(f"  Pipeline misses: {misses}")

        finally:
            _teardown_fixture("game_run", proc)
