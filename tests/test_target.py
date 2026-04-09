"""Tests for target parsing."""
from maa.define import OCRResult

from maafw_cli.core.target import parse_target, ResolvedTarget
from maafw_cli.core.element import ElementStore


def _make_store_with_elements():
    """Create an ElementStore pre-loaded with sample elements."""
    store = ElementStore()
    store.build_from_ocr([
        OCRResult(text="设置", box=[120, 45, 80, 24], score=0.97),
        OCRResult(text="显示", box=[120, 89, 72, 24], score=0.95),
    ])
    return store


class TestParseTarget:
    def test_coord_target(self):
        store = ElementStore()
        result = parse_target("452,387", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (452, 387, 0, 0)
        assert result.center == (452, 387)
        assert "coords" in result.source

    def test_coord_with_spaces(self):
        store = ElementStore()
        result = parse_target(" 100 , 200 ", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (100, 200, 0, 0)

    def test_box_target(self):
        store = ElementStore()
        result = parse_target("10,20,30,40", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (10, 20, 30, 40)
        assert result.center == (25, 40)
        assert "box" in result.source

    def test_element_target(self):
        store = _make_store_with_elements()
        result = parse_target("e1", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (120, 45, 80, 24)
        assert result.center == (160, 57)
        assert "ref:e1" in result.source

    def test_element_case_insensitive(self):
        store = _make_store_with_elements()
        result = parse_target("E2", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (120, 89, 72, 24)

    def test_element_unknown(self):
        store = _make_store_with_elements()
        result = parse_target("e99", store)
        assert isinstance(result, str)
        assert "Unknown" in result

    def test_invalid_target(self):
        store = ElementStore()
        result = parse_target("foobar", store)
        assert isinstance(result, str)
        assert "Cannot parse" in result

    def test_empty_target(self):
        store = ElementStore()
        result = parse_target("  ", store)
        assert isinstance(result, str)

    def test_negative_coords(self):
        """Negative coordinates should be supported (Win32 multi-monitor)."""
        store = ElementStore()
        result = parse_target("-100,200", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (-100, 200, 0, 0)

    def test_both_negative_coords(self):
        store = ElementStore()
        result = parse_target("-50,-30", store)
        assert isinstance(result, ResolvedTarget)
        assert result.box == (-50, -30, 0, 0)
