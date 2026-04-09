"""Tests for the Element system."""
from maa.define import BoxAndCountResult, BoxAndScoreResult, CustomRecognitionResult, OCRResult

from maafw_cli.core.element import Element, ElementStore


def _sample_ocr_results() -> list[OCRResult]:
    return [
        OCRResult(text="设置", box=[120, 45, 80, 24], score=0.97),
        OCRResult(text="显示", box=[120, 89, 72, 24], score=0.95),
        OCRResult(text="亮度", box=[120, 133, 96, 24], score=0.93),
    ]


class TestElement:
    def test_center(self):
        r = Element(ref="e1", text="hi", box=[100, 200, 40, 20], score=0.9)
        assert r.center == (120, 210)

    def test_to_dict(self):
        r = Element(ref="e1", text="A", box=[0, 0, 10, 10], score=0.5)
        d = r.to_dict()
        assert d == {"ref": "e1", "text": "A", "box": [0, 0, 10, 10], "score": 0.5}


class TestElementStore:
    def test_build_from_ocr(self):
        store = ElementStore()
        refs = store.build_from_ocr(_sample_ocr_results())

        assert len(refs) == 3
        assert refs[0].ref == "e1"
        assert refs[0].text == "设置"
        assert refs[1].ref == "e2"
        assert refs[2].ref == "e3"
        assert refs[2].score == 0.93

    def test_resolve(self):
        store = ElementStore()
        store.build_from_ocr(_sample_ocr_results())

        assert store.resolve("e1") is not None
        assert store.resolve("e1").text == "设置"
        assert store.resolve("e2").text == "显示"
        assert store.resolve("e99") is None

    def test_elements_property(self):
        store = ElementStore()
        store.build_from_ocr(_sample_ocr_results())
        elems = store.elements
        assert len(elems) == 3
        assert elems[0].ref == "e1"
        # elements returns a copy
        elems.clear()
        assert len(store.elements) == 3


# ── Element count field ──────────────────────────────────────────


class TestElementCount:
    def test_to_dict_with_count(self):
        e = Element(ref="e1", text=None, box=[0, 0, 10, 10], score=0.0, count=42)
        d = e.to_dict()
        assert d["count"] == 42

    def test_to_dict_without_count(self):
        e = Element(ref="e1", text="hi", box=[0, 0, 10, 10], score=0.9)
        d = e.to_dict()
        assert "count" not in d  # count=None is excluded

    def test_to_dict_existing_element_unchanged(self):
        """Existing OCR-style elements still produce the same dict shape."""
        e = Element(ref="e1", text="A", box=[0, 0, 10, 10], score=0.5)
        d = e.to_dict()
        assert d == {"ref": "e1", "text": "A", "box": [0, 0, 10, 10], "score": 0.5}

    def test_center_with_count(self):
        e = Element(ref="e1", text=None, box=[100, 200, 40, 20], score=0.5, count=10)
        assert e.center == (120, 210)


# ── build_from_results ───────────────────────────────────────────


class TestBuildFromResults:
    def test_template_match_results(self):
        results = [BoxAndScoreResult(box=[10, 20, 30, 40], score=0.95)]
        store = ElementStore()
        elems = store.build_from_results(results, "TemplateMatch")
        assert len(elems) == 1
        assert elems[0].ref == "e1"
        assert elems[0].text is None
        assert elems[0].score == 0.95
        assert elems[0].count is None

    def test_color_match_results(self):
        results = [BoxAndCountResult(box=[10, 20, 30, 40], count=1542)]
        store = ElementStore()
        elems = store.build_from_results(results, "ColorMatch")
        assert elems[0].score == 0.0
        assert elems[0].count == 1542
        assert elems[0].text is None

    def test_feature_match_results(self):
        results = [BoxAndCountResult(box=[5, 10, 15, 20], count=8)]
        store = ElementStore()
        elems = store.build_from_results(results, "FeatureMatch")
        assert elems[0].count == 8

    def test_ocr_results(self):
        results = [OCRResult(box=[10, 20, 30, 40], score=0.97, text="设置")]
        store = ElementStore()
        elems = store.build_from_results(results, "OCR")
        assert elems[0].text == "设置"
        assert elems[0].score == 0.97
        assert elems[0].count is None

    def test_sequential_refs(self):
        results = [BoxAndScoreResult(box=[i, 0, 10, 10], score=0.5) for i in range(5)]
        store = ElementStore()
        elems = store.build_from_results(results, "TemplateMatch")
        assert [e.ref for e in elems] == ["e1", "e2", "e3", "e4", "e5"]

    def test_empty_results(self):
        store = ElementStore()
        elems = store.build_from_results([], "TemplateMatch")
        assert elems == []

    def test_custom_results(self):
        results = [
            CustomRecognitionResult(
                box=[10, 20, 30, 40],
                detail={"text": "START", "score": 0.88, "count": 2},
            )
        ]
        store = ElementStore()
        elems = store.build_from_results(results, "Custom")
        assert len(elems) == 1
        assert elems[0].ref == "e1"
        assert elems[0].text == "START"
        assert elems[0].score == 0.88
        assert elems[0].count == 2

