"""
Integration tests for the clicking game — CLI-level validation.

Strategy: **CLI-first** — each recognition / action step is validated as a
standalone ``reco`` or ``click`` CLI command, plus pipeline structure checks.

Screens:
1. Start  — "CLICKING GAME" + "PLAY" button  (OCR)
2. Game   — target icon hint + 3 icon buttons (TemplateMatch + green_mask)
3. Over   — "GAME OVER" + "Score: N" + "Misses: N" (OCR)

    uv run pytest tests/integration/test_clicking_game.py -m integration -v -s
"""
from __future__ import annotations

import re
import time

import pytest

from maafw_cli.cli import cli
from .conftest import (
    _PIPELINE_FIXTURES_DIR,
    parse_json_output,
    runner,
    safe_print,
)

_GAME_PIPELINE_DIR = str(_PIPELINE_FIXTURES_DIR)

_GAME_NODES = {
    "ClickPlay", "WaitGameScreen", "GameLoop", "GameOver_Detect",
    "Target_APPLE", "Target_LEMON", "Target_GRAPE",
    "Click_APPLE", "Click_LEMON", "Click_GRAPE",
    "CursorReset", "ReadScore",
}


# ═════════════════════════════════════════════════════════════════
# Group 1: CLI-level validation of individual pipeline steps
# ═════════════════════════════════════════════════════════════════


class TestGameCliSteps:
    """Validate individual reco/click commands against the game window.

    These tests run in order within the class — each builds on the previous
    state of the game window.
    """

    # ── Start screen ──────────────────────────────────────────

    def test_01_ocr_sees_clicking_game(self, game_window):
        """OCR should see 'CLICKING' or 'GAME' title on start screen."""
        result = runner.invoke(cli, ["--on", "game", "--json", "reco", "OCR"])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        all_text = " ".join(r["text"] for r in data["results"])
        assert "CLICK" in all_text or "GAME" in all_text, (
            f"Expected 'CLICKING GAME' on start screen, got: {all_text}"
        )

    def test_02_ocr_sees_play_button(self, game_window):
        """OCR should find 'PLAY' on start screen."""
        result = runner.invoke(cli, [
            "--on", "game", "--json", "reco", "OCR", "expected=PLAY",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        play_results = [r for r in data["results"] if "PLAY" in r["text"]]
        assert len(play_results) >= 1, "OCR should find 'PLAY'"

    def test_03_click_play_enters_game(self, game_window):
        """Clicking 'PLAY' should transition to game screen."""
        # Find PLAY
        r = runner.invoke(cli, [
            "--on", "game", "--json", "reco", "OCR", "expected=PLAY",
        ])
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        play = [x for x in data["results"] if "PLAY" in x["text"]][0]
        ref = play["ref"]

        # Click it
        r = runner.invoke(cli, ["--on", "game", "click", ref])
        safe_print(r.output)
        assert r.exit_code == 0

        # Wait for game screen
        time.sleep(1.0)

        # Verify game screen: should see "Time" and "Score"
        r = runner.invoke(cli, ["--on", "game", "--json", "reco", "OCR"])
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        all_text = " ".join(r_["text"] for r_ in data["results"])
        assert "Time" in all_text or "Score" in all_text, (
            f"Expected game screen (Time/Score), got: {all_text}"
        )

    # ── Game screen (TemplateMatch + green_mask) ──────────────

    def test_04_template_match_hint_area(self, game_window):
        """TemplateMatch + green_mask should find one icon in the hint area."""
        found = False
        for icon in ["game_apple_mask.png", "game_lemon_mask.png", "game_grape_mask.png"]:
            r = runner.invoke(cli, [
                "--on", "game", "--json", "reco", "TemplateMatch",
                f"template={icon}", "roi=150,60,660,130",
                "green_mask=true", "threshold=0.7",
            ])
            if r.exit_code == 0:
                data = parse_json_output(r.output)
                if data["results"] and data["results"][0]["score"] >= 0.7:
                    found = True
                    safe_print(f"  Hint matched: {icon} score={data['results'][0]['score']:.3f}")
                    break
        assert found, "TemplateMatch should find a target icon in hint area"

    def test_05_template_match_game_area(self, game_window):
        """TemplateMatch + green_mask should find all 3 icons in game area."""
        results_per_icon = {}
        for icon in ["game_apple_mask.png", "game_lemon_mask.png", "game_grape_mask.png"]:
            r = runner.invoke(cli, [
                "--on", "game", "--json", "reco", "TemplateMatch",
                f"template={icon}", "roi=0,200,960,400",
                "green_mask=true", "threshold=0.7",
            ])
            if r.exit_code == 0:
                data = parse_json_output(r.output)
                hits = [x for x in data["results"] if x["score"] >= 0.7]
                if hits:
                    results_per_icon[icon] = hits[0]
                    safe_print(f"  Game area: {icon} score={hits[0]['score']:.3f} box={hits[0]['box']}")
        assert len(results_per_icon) >= 3, (
            f"Expected 3 icons in game area, found {len(results_per_icon)}: "
            f"{list(results_per_icon.keys())}"
        )

    def test_06_click_correct_icon_scores(self, game_window):
        """Find target, click matching icon — score should increase."""
        # Read current score
        r = runner.invoke(cli, ["--on", "game", "--json", "reco", "OCR"])
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        score_results = [x for x in data["results"] if "Score" in x.get("text", "")]
        old_score = 0
        if score_results:
            m = re.search(r"(\d+)", score_results[0]["text"])
            if m:
                old_score = int(m.group(1))

        # Find target icon in hint area
        target_icon = None
        for icon in ["game_apple_mask.png", "game_lemon_mask.png", "game_grape_mask.png"]:
            r = runner.invoke(cli, [
                "--on", "game", "--json", "reco", "TemplateMatch",
                f"template={icon}", "roi=150,60,660,130",
                "green_mask=true", "threshold=0.7",
            ])
            if r.exit_code == 0:
                data = parse_json_output(r.output)
                if data["results"] and data["results"][0]["score"] >= 0.7:
                    target_icon = icon
                    break
        assert target_icon is not None, "Could not identify target icon"

        # Find & click that icon in game area
        r = runner.invoke(cli, [
            "--on", "game", "--json", "reco", "TemplateMatch",
            f"template={target_icon}", "roi=0,200,960,400",
            "green_mask=true", "threshold=0.7",
        ])
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        assert data["results"], f"Icon {target_icon} not found in game area"
        ref = data["results"][0]["ref"]

        r = runner.invoke(cli, ["--on", "game", "click", ref])
        safe_print(r.output)
        assert r.exit_code == 0

        # Move cursor away (avoid interfering with next TemplateMatch)
        r = runner.invoke(cli, ["--on", "game", "click", "480,680"])
        assert r.exit_code == 0

        time.sleep(0.3)

        # Verify score increased
        r = runner.invoke(cli, ["--on", "game", "--json", "reco", "OCR"])
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        score_results = [x for x in data["results"] if "Score" in x.get("text", "")]
        new_score = 0
        if score_results:
            m = re.search(r"(\d+)", score_results[0]["text"])
            if m:
                new_score = int(m.group(1))
        assert new_score > old_score, (
            f"Score should increase: {old_score} -> {new_score}"
        )

    # ── Wait for game over ────────────────────────────────────

    def test_07_game_over_detected(self, game_window):
        """Wait for game over and verify OCR sees 'GAME OVER'."""
        game_over = False
        for _ in range(25):
            r = runner.invoke(cli, ["--on", "game", "--json", "reco", "OCR"])
            if r.exit_code == 0:
                data = parse_json_output(r.output)
                all_text = " ".join(r_["text"] for r_ in data["results"])
                if "GAME" in all_text and "OVER" in all_text:
                    game_over = True
                    safe_print(f"  Game over! Text: {all_text}")
                    break
            time.sleep(1)
        assert game_over, "Game should end after 20s"

    def test_08_read_final_score_and_misses(self, game_window):
        """OCR should find Score and Misses on game over screen."""
        r = runner.invoke(cli, ["--on", "game", "--json", "reco", "OCR"])
        safe_print(r.output)
        assert r.exit_code == 0
        data = parse_json_output(r.output)
        all_text = " ".join(r_["text"] for r_ in data["results"])

        m = re.search(r"Score:\s*(\d+)", all_text)
        assert m, f"Could not find Score in: {all_text}"
        score = int(m.group(1))
        safe_print(f"  Final score: {score}")
        assert score >= 1, f"Score should be >= 1, got {score}"

        m = re.search(r"Misses:\s*(\d+)", all_text)
        assert m, f"Could not find Misses in: {all_text}"
        misses = int(m.group(1))
        safe_print(f"  Misses: {misses}")


# ═════════════════════════════════════════════════════════════════
# Group 2: Pipeline validation
# ═════════════════════════════════════════════════════════════════


class TestGamePipelineSetup:
    """Validate the clicking game pipeline JSON."""

    def test_validate_pipeline(self, game_window):
        result = runner.invoke(cli, [
            "--on", "game", "--json", "pipeline", "validate", _GAME_PIPELINE_DIR,
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["valid"] is True

    def test_list_game_nodes(self, game_window):
        result = runner.invoke(cli, ["--on", "game", "--json", "pipeline", "list"])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        loaded = set(data["nodes"])
        assert _GAME_NODES.issubset(loaded), f"Missing: {_GAME_NODES - loaded}"

    def test_show_gameloop_node(self, game_window):
        result = runner.invoke(cli, [
            "--on", "game", "--json", "pipeline", "show", "GameLoop",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        defn = data["definition"]
        reco_type = defn["recognition"]
        if isinstance(reco_type, dict):
            reco_type = reco_type["type"]
        assert reco_type == "DirectHit"
        assert len(defn["next"]) == 4
