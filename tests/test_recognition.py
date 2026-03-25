"""Tests for maafw/recognition.py — generic recognition layer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maafw_cli.core.errors import RecognitionError
from maafw_cli.maafw.recognition import (
    build_params,
    build_params_from_raw,
    recognize,
)
from maa.pipeline import JColorMatch, JFeatureMatch, JOCR, JTemplateMatch


# ── build_params tests ───────────────────────────────────────────


class TestBuildParams:
    """Test parameter string → J* parameter object conversion."""

    def test_template_match_params(self):
        obj = build_params("TemplateMatch", {
            "template": "a.png,b.png",
            "roi": "0,0,400,200",
            "threshold": "0.8",
        })
        assert isinstance(obj, JTemplateMatch)
        assert obj.template == ["a.png", "b.png"]
        assert obj.roi == (0, 0, 400, 200)
        assert obj.threshold == [0.8]

    def test_template_match_missing_template(self):
        with pytest.raises(RecognitionError, match="template"):
            build_params("TemplateMatch", {})

    def test_feature_match_params(self):
        obj = build_params("FeatureMatch", {
            "template": "icon.png",
            "ratio": "0.7",
        })
        assert isinstance(obj, JFeatureMatch)
        assert obj.template == ["icon.png"]
        assert obj.ratio == 0.7

    def test_feature_match_missing_template(self):
        with pytest.raises(RecognitionError, match="template"):
            build_params("FeatureMatch", {})

    def test_color_match_params(self):
        obj = build_params("ColorMatch", {
            "lower": "200,0,0",
            "upper": "255,50,50",
        })
        assert isinstance(obj, JColorMatch)
        assert obj.lower == [[200, 0, 0]]
        assert obj.upper == [[255, 50, 50]]

    def test_color_match_missing_lower(self):
        with pytest.raises(RecognitionError, match="lower.*upper"):
            build_params("ColorMatch", {"lower": "0,0,0"})

    def test_color_match_missing_upper(self):
        with pytest.raises(RecognitionError, match="lower.*upper"):
            build_params("ColorMatch", {"upper": "255,255,255"})

    def test_ocr_params(self):
        obj = build_params("OCR", {
            "expected": "设置,显示",
            "roi": "0,0,400,200",
        })
        assert isinstance(obj, JOCR)
        assert obj.expected == ["设置", "显示"]
        assert obj.roi == (0, 0, 400, 200)

    def test_ocr_no_params(self):
        obj = build_params("OCR", {})
        assert isinstance(obj, JOCR)

    def test_unknown_type_raises(self):
        with pytest.raises(RecognitionError, match="Unknown recognition type"):
            build_params("UnknownType", {})

    def test_template_match_with_green_mask(self):
        obj = build_params("TemplateMatch", {
            "template": "btn.png",
            "green_mask": "true",
        })
        assert obj.green_mask is True

    def test_ocr_with_threshold(self):
        obj = build_params("OCR", {"threshold": "0.5"})
        assert obj.threshold == 0.5


class TestBuildParamsFromRaw:
    """Test raw JSON → params conversion."""

    def test_raw_template_match(self):
        reco_type, obj = build_params_from_raw(
            '{"recognition":"TemplateMatch","template":["b.png"]}'
        )
        assert reco_type == "TemplateMatch"
        assert isinstance(obj, JTemplateMatch)
        assert obj.template == ["b.png"]

    def test_raw_ocr(self):
        reco_type, obj = build_params_from_raw(
            '{"recognition":"OCR","expected":["设置"]}'
        )
        assert reco_type == "OCR"
        assert isinstance(obj, JOCR)
        assert obj.expected == ["设置"]

    def test_raw_color_match(self):
        reco_type, obj = build_params_from_raw(
            '{"recognition":"ColorMatch","lower":[[200,0,0]],"upper":[[255,50,50]]}'
        )
        assert reco_type == "ColorMatch"
        assert isinstance(obj, JColorMatch)

    def test_raw_invalid_json(self):
        with pytest.raises(RecognitionError, match="Invalid JSON"):
            build_params_from_raw("{bad json}")

    def test_raw_missing_recognition_key(self):
        with pytest.raises(RecognitionError, match="recognition"):
            build_params_from_raw('{"template":["a.png"]}')

    def test_raw_unknown_type(self):
        with pytest.raises(RecognitionError, match="Unknown recognition type"):
            build_params_from_raw('{"recognition":"FakeType"}')


# ── recognize() tests ────────────────────────────────────────────


class TestRecognize:
    """Test maafw/recognition.py::recognize()."""

    def _mock_recognition_pipeline(
        self, *, all_results=None, info=None, tasker=None, image="fake_img",
        ocr_exists=True,
    ):
        """Helper to set up mocks for the recognize pipeline."""
        from maafw_cli.maafw import recognition as mod

        if all_results is not None and info is None:
            mock_detail = MagicMock()
            mock_node = MagicMock()
            mock_node.recognition.all_results = all_results
            mock_detail.nodes = [mock_node]
            info = mock_detail

        mock_tasker = MagicMock() if tasker is None else tasker
        if info is not None:
            mock_tasker.post_recognition.return_value.wait.return_value.get.return_value = info

        patches = {
            "_get_tasker": patch.object(mod, "_get_tasker", return_value=mock_tasker),
            "screencap": patch.object(mod, "screencap", return_value=image),
            "ocr_check": patch.object(mod, "check_ocr_files_exist", return_value=ocr_exists),
        }
        return patches

    def test_template_match_returns_results(self):
        from maa.define import BoxAndScoreResult
        fake_results = [BoxAndScoreResult(box=[10, 20, 30, 40], score=0.95)]

        patches = self._mock_recognition_pipeline(all_results=fake_results)
        with patches["_get_tasker"], patches["screencap"], patches["ocr_check"]:
            reco_type, results = recognize(
                MagicMock(), "TemplateMatch", {"template": "btn.png"}
            )
        assert reco_type == "TemplateMatch"
        assert len(results) == 1
        assert results[0].score == 0.95

    def test_color_match_returns_results(self):
        from maa.define import BoxAndCountResult
        fake_results = [BoxAndCountResult(box=[100, 200, 50, 50], count=1542)]

        patches = self._mock_recognition_pipeline(all_results=fake_results)
        with patches["_get_tasker"], patches["screencap"], patches["ocr_check"]:
            reco_type, results = recognize(
                MagicMock(), "ColorMatch", {"lower": "200,0,0", "upper": "255,50,50"}
            )
        assert reco_type == "ColorMatch"
        assert len(results) == 1
        assert results[0].count == 1542

    def test_ocr_returns_results(self):
        from maa.define import OCRResult
        fake_results = [OCRResult(box=[10, 20, 30, 40], score=0.97, text="设置")]

        patches = self._mock_recognition_pipeline(all_results=fake_results, ocr_exists=True)
        with patches["_get_tasker"], patches["screencap"], patches["ocr_check"]:
            reco_type, results = recognize(MagicMock(), "OCR", {})
        assert reco_type == "OCR"
        assert results[0].text == "设置"

    def test_raw_json_passthrough(self):
        from maa.define import BoxAndScoreResult
        fake_results = [BoxAndScoreResult(box=[1, 2, 3, 4], score=0.5)]

        patches = self._mock_recognition_pipeline(all_results=fake_results)
        with patches["_get_tasker"], patches["screencap"], patches["ocr_check"]:
            reco_type, results = recognize(
                MagicMock(), reco_type="",
                raw='{"recognition":"TemplateMatch","template":["b.png"]}'
            )
        assert reco_type == "TemplateMatch"

    def test_unknown_reco_type_raises(self):
        with pytest.raises(RecognitionError, match="Unknown recognition type"):
            recognize(MagicMock(), "UnknownType", {})

    def test_screenshot_failure_raises(self):
        from maafw_cli.maafw import recognition as mod
        with patch.object(mod, "_get_tasker", return_value=MagicMock()), \
             patch.object(mod, "screencap", return_value=None), \
             patch.object(mod, "check_ocr_files_exist", return_value=True):
            with pytest.raises(RecognitionError, match="Screenshot failed"):
                recognize(MagicMock(), "TemplateMatch", {"template": "a.png"})

    def test_tasker_init_failure_raises(self):
        from maafw_cli.maafw import recognition as mod
        with patch.object(mod, "_get_tasker", return_value=None), \
             patch.object(mod, "check_ocr_files_exist", return_value=True):
            with pytest.raises(RecognitionError, match="tasker"):
                recognize(MagicMock(), "TemplateMatch", {"template": "a.png"})

    def test_empty_nodes_raises(self):
        from maafw_cli.maafw import recognition as mod
        mock_detail = MagicMock()
        mock_detail.nodes = []

        mock_tasker = MagicMock()
        mock_tasker.post_recognition.return_value.wait.return_value.get.return_value = mock_detail

        with patch.object(mod, "_get_tasker", return_value=mock_tasker), \
             patch.object(mod, "screencap", return_value="fake_img"), \
             patch.object(mod, "check_ocr_files_exist", return_value=True):
            with pytest.raises(RecognitionError, match="empty nodes"):
                recognize(MagicMock(), "TemplateMatch", {"template": "a.png"})

    def test_no_reco_type_and_no_raw_raises(self):
        with pytest.raises(RecognitionError, match="required"):
            recognize(MagicMock(), reco_type="", params={})

    def test_ocr_without_model_raises(self):
        from maafw_cli.maafw import recognition as mod
        with patch.object(mod, "check_ocr_files_exist", return_value=False):
            with pytest.raises(RecognitionError, match="OCR model not found"):
                recognize(MagicMock(), "OCR", {})
