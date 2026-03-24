"""Tests for target parsing."""
import tempfile
from pathlib import Path

from maa.define import OCRResult

from maafw_cli.core.target import parse_target, ResolvedTarget
from maafw_cli.core.textref import TextRefStore


def _make_store_with_refs():
    """Create a TextRefStore pre-loaded with sample refs."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    store = TextRefStore(path)
    store.build_from_ocr([
        OCRResult(text="设置", box=[120, 45, 80, 24], score=0.97),
        OCRResult(text="显示", box=[120, 89, 72, 24], score=0.95),
    ])
    store.save()
    return store, path


class TestParseTarget:
    def test_coord_target(self):
        store = TextRefStore(Path("/tmp/dummy.json"))
        result = parse_target("452,387", store)
        assert isinstance(result, ResolvedTarget)
        assert result.x == 452
        assert result.y == 387
        assert "coords" in result.source

    def test_coord_with_spaces(self):
        store = TextRefStore(Path("/tmp/dummy.json"))
        result = parse_target(" 100 , 200 ", store)
        assert isinstance(result, ResolvedTarget)
        assert result.x == 100
        assert result.y == 200

    def test_textref_target(self):
        store, path = _make_store_with_refs()
        result = parse_target("t1", store)
        assert isinstance(result, ResolvedTarget)
        # center of [120, 45, 80, 24] → (160, 57)
        assert result.x == 160
        assert result.y == 57
        assert "ref:t1" in result.source
        path.unlink(missing_ok=True)

    def test_textref_case_insensitive(self):
        store, path = _make_store_with_refs()
        result = parse_target("T2", store)
        assert isinstance(result, ResolvedTarget)
        path.unlink(missing_ok=True)

    def test_textref_unknown(self):
        store, path = _make_store_with_refs()
        result = parse_target("t99", store)
        assert isinstance(result, str)
        assert "Unknown" in result
        path.unlink(missing_ok=True)

    def test_invalid_target(self):
        store = TextRefStore(Path("/tmp/dummy.json"))
        result = parse_target("foobar", store)
        assert isinstance(result, str)
        assert "Cannot parse" in result

    def test_empty_target(self):
        store = TextRefStore(Path("/tmp/dummy.json"))
        result = parse_target("  ", store)
        assert isinstance(result, str)
