"""
Element system — short references (e1, e2, …) for recognition results.

Each recognition run (OCR, TemplateMatch, etc.) assigns sequential refs.
Refs are kept in memory so later commands (e.g. ``click e2``) can resolve
them without re-running recognition.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any

from maa.define import BoxAndCountResult, BoxAndScoreResult, CustomRecognitionResult, OCRResult


_log = logging.getLogger("maafw_cli.element")


@dataclass
class Element:
    """A single recognition result with a short reference id."""
    ref: str                # e.g. "e1"
    text: str | None        # recognised text (None for non-OCR results)
    box: list[int]          # [x, y, w, h]
    score: float            # confidence 0-1
    count: int | None = None  # ColorMatch/FeatureMatch result count

    @property
    def center(self) -> tuple[int, int]:
        """Return the centre point of the bounding box."""
        x, y, w, h = self.box
        return x + w // 2, y + h // 2

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["count"] is None:
            del d["count"]
        return d


class ElementStore:
    """Manages the current set of Elements (pure in-memory)."""

    def __init__(self) -> None:
        self._elements: list[Element] = []

    # ── building ────────────────────────────────────────────────

    def build_from_ocr(self, ocr_results: list[OCRResult]) -> list[Element]:
        """Convert MaaFW ``OCRResult`` objects into numbered Elements."""
        elements: list[Element] = []
        for i, r in enumerate(ocr_results, start=1):
            box = list(r.box) if isinstance(r.box, (list, tuple)) else [0, 0, 0, 0]
            elem = Element(
                ref=f"e{i}",
                text=str(r.text),
                box=[int(v) for v in box],
                score=round(float(r.score), 4),
            )
            elements.append(elem)
        self._elements = elements
        return elements

    def build_from_results(
        self, results: list, reco_type: str,
    ) -> list[Element]:
        """Convert generic recognition results into numbered Elements.

        Handles ``BoxAndScoreResult`` (TemplateMatch), ``BoxAndCountResult``
        (ColorMatch, FeatureMatch), ``OCRResult``, and
        ``CustomRecognitionResult``.

        """
        elements: list[Element] = []
        for i, r in enumerate(results, start=1):
            box = list(r.box) if isinstance(r.box, (list, tuple)) else [0, 0, 0, 0]
            box = [int(v) for v in box]

            if isinstance(r, OCRResult):
                elem = Element(
                    ref=f"e{i}",
                    text=str(r.text),
                    box=box,
                    score=round(float(r.score), 4),
                )
            elif isinstance(r, BoxAndCountResult):
                elem = Element(
                    ref=f"e{i}",
                    text=None,
                    box=box,
                    score=0.0,
                    count=int(r.count),
                )
            elif isinstance(r, BoxAndScoreResult):
                elem = Element(
                    ref=f"e{i}",
                    text=None,
                    box=box,
                    score=round(float(r.score), 4),
                )
            elif isinstance(r, CustomRecognitionResult):
                detail = r.detail if isinstance(r.detail, dict) else {}

                text = detail.get("text") if isinstance(detail.get("text"), str) else None
                score = detail.get("score")
                count = detail.get("count")
                elem = Element(
                    ref=f"e{i}",
                    text=text,
                    box=box,
                    score=round(float(score), 4) if isinstance(score, (int, float)) else 1.0,
                    count=int(count) if isinstance(count, int) else None,
                )
            else:
                _log.warning("Unknown result type %s, skipping", type(r).__name__)
                continue

            elements.append(elem)
        self._elements = elements
        return elements

    # ── lookup ──────────────────────────────────────────────────

    def resolve(self, ref_id: str) -> Element | None:
        """Find an Element by its short id (e.g. ``"e2"``)."""
        for e in self._elements:
            if e.ref == ref_id:
                return e
        return None

    @property
    def elements(self) -> list[Element]:
        return list(self._elements)
