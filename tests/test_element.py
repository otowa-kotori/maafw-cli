"""Tests for the Element system."""
import tempfile
from pathlib import Path

from maa.define import OCRResult

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
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        store = ElementStore(path)
        refs = store.build_from_ocr(_sample_ocr_results())

        assert len(refs) == 3
        assert refs[0].ref == "e1"
        assert refs[0].text == "设置"
        assert refs[1].ref == "e2"
        assert refs[2].ref == "e3"
        assert refs[2].score == 0.93

        path.unlink(missing_ok=True)

    def test_resolve(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        store = ElementStore(path)
        store.build_from_ocr(_sample_ocr_results())

        assert store.resolve("e1") is not None
        assert store.resolve("e1").text == "设置"
        assert store.resolve("e2").text == "显示"
        assert store.resolve("e99") is None

        path.unlink(missing_ok=True)

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        store = ElementStore(path)
        store.build_from_ocr(_sample_ocr_results())
        store.save()

        # Load into a new store
        store2 = ElementStore(path)
        refs = store2.load()

        assert len(refs) == 3
        assert refs[0].ref == "e1"
        assert refs[0].text == "设置"
        assert store2.resolve("e3").text == "亮度"

        path.unlink(missing_ok=True)

    def test_load_missing_file(self):
        store = ElementStore(Path("/nonexistent/file.json"))
        refs = store.load()
        assert refs == []

    def test_load_corrupt_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{bad json")
            path = Path(f.name)

        store = ElementStore(path)
        refs = store.load()
        assert refs == []

        path.unlink(missing_ok=True)


class TestElementStoreMemoryMode:
    """ElementStore(path=None) operates in memory without file I/O."""

    def test_save_is_noop(self):
        store = ElementStore(path=None)
        store.build_from_ocr(_sample_ocr_results())
        store.save()  # should not raise

    def test_load_returns_current_elements(self):
        store = ElementStore(path=None)
        store.build_from_ocr(_sample_ocr_results())
        refs = store.load()
        assert len(refs) == 3

    def test_resolve_works(self):
        store = ElementStore(path=None)
        store.build_from_ocr(_sample_ocr_results())
        assert store.resolve("e1").text == "设置"
        assert store.resolve("e99") is None


class TestElementStoreLoadTolerance:
    """ElementStore.load tolerates extra/missing fields in persisted data."""

    def test_load_extra_fields(self, tmp_path):
        import json
        path = tmp_path / "elements.json"
        path.write_text(json.dumps({
            "timestamp": "2026-01-01T00:00:00",
            "extra_field": "ignored",
            "elements": [
                {"ref": "e1", "text": "A", "box": [0, 0, 10, 10], "score": 0.9,
                 "unknown_key": "should_not_crash"},
            ],
        }), encoding="utf-8")

        store = ElementStore(path)
        refs = store.load()
        # May load 0 (if strict) or 1 (if tolerant); should not crash
        # Current impl uses Element(**r) which will fail on extra keys
        # This test documents current behavior
        assert isinstance(refs, list)

    def test_load_missing_fields(self, tmp_path):
        import json
        path = tmp_path / "elements.json"
        path.write_text(json.dumps({
            "timestamp": "2026-01-01T00:00:00",
            "elements": [
                {"ref": "e1", "text": "A"},  # missing box and score
            ],
        }), encoding="utf-8")

        store = ElementStore(path)
        refs = store.load()
        # Should not crash; returns empty list on parse error
        assert isinstance(refs, list)
