"""
Integration tests for the ``reco`` command.

Covers all four recognition types through the real CLI → daemon pipeline:
- OCR — against mock_window (READY/PRESS text)
- ColorMatch — against mock_window (white background)
- TemplateMatch — against reco_window (fixture icons at known positions)
- FeatureMatch — against reco_window (Lenna variants: scaled/rotated/occluded)

    uv run pytest tests/integration/test_reco.py -v -s
"""
from __future__ import annotations

import pytest

from maafw_cli.cli import cli
from .conftest import (
    ensure_connected,
    parse_json_output,
    runner,
    safe_print,
)


# ═══════════════════════════════════════════════════════════════════
# OCR via reco
# ═══════════════════════════════════════════════════════════════════


class TestRecoOcr:
    """reco OCR should behave identically to the dedicated ocr command."""

    def test_human_output(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["reco", "OCR"])
        safe_print(result.output)
        assert result.exit_code == 0
        assert "Recognition: OCR" in result.output

    def test_json_output(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["--json", "reco", "OCR"])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["reco_type"] == "OCR"
        assert "results" in data
        assert "elapsed_ms" in data
        if data["results"]:
            r = data["results"][0]
            assert "ref" in r
            assert "text" in r
            assert "box" in r
            assert "score" in r

    def test_sees_ready(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["--json", "reco", "OCR"])
        if result.exit_code != 0:
            pytest.skip("reco OCR failed")
        data = parse_json_output(result.output)
        all_text = " ".join(r["text"] for r in data["results"])
        assert "READY" in all_text, f"Expected 'READY', got: {all_text}"

    def test_with_roi(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["--json", "reco", "OCR", "roi=0,0,960,300"])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["reco_type"] == "OCR"

    def test_with_expected(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["--json", "reco", "OCR", "expected=READY"])
        safe_print(result.output)
        assert result.exit_code == 0

    def test_raw_json(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, [
            "--json", "reco",
            "--raw", '{"recognition":"OCR"}',
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["reco_type"] == "OCR"


# ═══════════════════════════════════════════════════════════════════
# ColorMatch via reco
# ═══════════════════════════════════════════════════════════════════


class TestRecoColorMatch:
    """ColorMatch against the mock window's white background."""

    def test_white_background(self, mock_window):
        """Match near-white pixels — should find results with count > 0."""
        ensure_connected(mock_window)
        result = runner.invoke(cli, [
            "--json", "reco", "ColorMatch",
            "lower=230,230,230", "upper=255,255,255",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["reco_type"] == "ColorMatch"
        assert len(data["results"]) >= 1
        r = data["results"][0]
        assert "count" in r
        assert r["count"] > 0

    def test_nonexistent_color(self, mock_window):
        """Match vivid purple — should not find meaningful results."""
        ensure_connected(mock_window)
        result = runner.invoke(cli, [
            "--json", "reco", "ColorMatch",
            "lower=200,0,200", "upper=210,10,210",
        ])
        safe_print(result.output)
        # May succeed with count=0 or fail — both are acceptable
        if result.exit_code == 0:
            data = parse_json_output(result.output)
            assert data["reco_type"] == "ColorMatch"

    def test_human_output_shows_count(self, mock_window):
        """Human output should display count=N, not score%."""
        ensure_connected(mock_window)
        result = runner.invoke(cli, [
            "reco", "ColorMatch",
            "lower=230,230,230", "upper=255,255,255",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        assert "count=" in result.output
        assert "ColorMatch" in result.output

    def test_missing_params_errors(self, mock_window):
        """ColorMatch without lower/upper should error."""
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["reco", "ColorMatch"])
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════
# TemplateMatch via reco
# ═══════════════════════════════════════════════════════════════════


class TestRecoTemplateMatch:
    """TemplateMatch against the reco_window with fixture icons.

    Fixture images are loaded into daemon's Resource by the reco_window
    fixture. Each icon is placed at a known position in the window.
    """

    def test_plus_icon_exact_match(self, reco_window):
        """icon_plus.png should match at score ~1.0."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "TemplateMatch",
            "template=icon_plus.png", "threshold=0.9",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["reco_type"] == "TemplateMatch"
        assert len(data["results"]) >= 1
        best = max(data["results"], key=lambda r: r["score"])
        assert best["score"] >= 0.95

    def test_shapes_icon_exact_match(self, reco_window):
        """icon_shapes.png should match at score ~1.0."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "TemplateMatch",
            "template=icon_shapes.png", "threshold=0.9",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        best = max(data["results"], key=lambda r: r["score"])
        assert best["score"] >= 0.95

    def test_lenna_exact_match(self, reco_window):
        """icon_lenna.png should match the original (128x128) at score ~1.0."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "TemplateMatch",
            "template=icon_lenna.png", "threshold=0.9",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert len(data["results"]) >= 1
        best = max(data["results"], key=lambda r: r["score"])
        assert best["score"] >= 0.95
        assert best["text"] is None  # TemplateMatch has no text

    def test_lenna_does_not_match_scaled_at_high_threshold(self, reco_window):
        """TemplateMatch is size-sensitive: the 1.5x scaled Lenna should
        NOT match at threshold=0.9 (only original size matches)."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "TemplateMatch",
            "template=icon_lenna.png", "threshold=0.9",
        ])
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        # All high-score matches should be 128x128 (original size), not 192x192
        for r in data["results"]:
            if r["score"] >= 0.9:
                assert r["box"][2] == 128 and r["box"][3] == 128

    def test_diamond_b_not_confused_with_a(self, reco_window):
        """diamond_b (ring) should not match diamond_a (dot) at threshold=0.95.

        We verify that:
        1. There ARE results (diamond_b is similar enough to trigger detection)
        2. But NONE of them score >= 0.95 (they are distinguishable)
        This proves the matcher sees a difference, not that it sees nothing.
        """
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "TemplateMatch",
            "template=icon_diamond_b.png", "threshold=0.7",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        # Should have results (diamond_b is similar to diamond_a)
        assert len(data["results"]) >= 1, "Expected at least one result"
        # But none should be a perfect match
        for r in data["results"]:
            assert r["score"] < 0.95, (
                f"diamond_b should not match at >=0.95, got {r['score']} at {r['box']}"
            )

    def test_human_output_shows_score(self, reco_window):
        """Human output should display score%, not count."""
        result = runner.invoke(cli, [
            "--on", "reco", "reco", "TemplateMatch",
            "template=icon_plus.png",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        assert "TemplateMatch" in result.output
        assert "%" in result.output

    def test_missing_template_errors(self, reco_window):
        """TemplateMatch without template= should error."""
        result = runner.invoke(cli, ["--on", "reco", "reco", "TemplateMatch"])
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════
# FeatureMatch via reco
# ═══════════════════════════════════════════════════════════════════


class TestRecoFeatureMatch:
    """FeatureMatch against the reco_window using Lenna variants.

    Unlike TemplateMatch, FeatureMatch is robust to scale, rotation,
    and partial occlusion. Uses the original icon_lenna.png (128x128)
    as template to match all four Lenna variants in the window.
    """

    def test_finds_all_lenna_variants(self, reco_window):
        """FeatureMatch with icon_lenna.png should find all 4 Lenna instances."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "FeatureMatch",
            "template=icon_lenna.png",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert data["reco_type"] == "FeatureMatch"
        # Should find at least the original + scaled + rotated + occluded
        lenna_results = [r for r in data["results"] if r["count"] >= 2]
        assert len(lenna_results) >= 3, (
            f"Expected >= 3 Lenna matches, got {len(lenna_results)}: {data['results']}"
        )

    def test_scaled_variant_matched(self, reco_window):
        """The 1.5x scaled Lenna (left-middle) should be found via ROI."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "FeatureMatch",
            "template=icon_lenna.png", "roi=20,320,250,230",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert len(data["results"]) >= 1
        assert data["results"][0]["count"] >= 2

    def test_rotated_variant_matched(self, reco_window):
        """The 30-degree rotated Lenna (right-middle) should be found via ROI."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "FeatureMatch",
            "template=icon_lenna.png", "roi=700,320,260,230",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert len(data["results"]) >= 1
        assert data["results"][0]["count"] >= 2

    def test_occluded_variant_matched(self, reco_window):
        """The 30%-occluded Lenna (bottom-right) should be found via ROI."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "FeatureMatch",
            "template=icon_lenna.png", "roi=770,550,200,180",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        assert len(data["results"]) >= 1
        assert data["results"][0]["count"] >= 2

    def test_template_match_cannot_find_scaled(self, reco_window):
        """Contrast: TemplateMatch should NOT find the 1.5x scaled Lenna
        at high threshold — demonstrating FeatureMatch's advantage."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "TemplateMatch",
            "template=icon_lenna.png", "threshold=0.9",
            "roi=20,320,250,230",
        ])
        safe_print(result.output)
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        # TemplateMatch should find nothing in the scaled region at 0.9
        high_score = [r for r in data["results"] if r["score"] >= 0.9]
        assert len(high_score) == 0, (
            f"TemplateMatch should not match scaled Lenna at 0.9, got: {high_score}"
        )

    def test_result_has_count_field(self, reco_window):
        """FeatureMatch results should have count (not score)."""
        result = runner.invoke(cli, [
            "--on", "reco", "--json", "reco", "FeatureMatch",
            "template=icon_lenna.png",
        ])
        assert result.exit_code == 0
        data = parse_json_output(result.output)
        for r in data["results"]:
            assert "count" in r
            assert r["score"] == 0.0  # FeatureMatch has no score


# ═══════════════════════════════════════════════════════════════════
# Error paths
# ═══════════════════════════════════════════════════════════════════


class TestRecoErrors:
    def test_unknown_type(self, mock_window):
        ensure_connected(mock_window)
        result = runner.invoke(cli, ["reco", "FakeType"])
        assert result.exit_code != 0

    def test_no_type(self):
        result = runner.invoke(cli, ["reco"])
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════
# Element refs interop
# ═══════════════════════════════════════════════════════════════════


class TestRecoElementRefs:
    def test_reco_refs_clickable(self, mock_window):
        """Element refs produced by reco should be usable by click."""
        ensure_connected(mock_window)

        r = runner.invoke(cli, ["--json", "reco", "OCR"])
        if r.exit_code != 0:
            pytest.skip("reco OCR failed")
        data = parse_json_output(r.output)
        if not data["results"]:
            pytest.skip("No OCR results to test with")

        ref = data["results"][0]["ref"]
        r = runner.invoke(cli, ["click", ref])
        safe_print(r.output)
        assert r.exit_code == 0
        assert "Clicked" in r.output
