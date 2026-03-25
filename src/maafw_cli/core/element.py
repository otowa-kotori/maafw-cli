"""
Element system — short references (e1, e2, …) for recognition results.

Each recognition run (OCR, TemplateMatch, etc.) assigns sequential refs.
Refs are persisted to ``elements.json`` so later commands (e.g. ``click e2``)
can resolve them without re-running recognition.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maa.define import OCRResult

_log = logging.getLogger("maafw_cli.element")


@dataclass
class Element:
    """A single recognition result with a short reference id."""
    ref: str                # e.g. "e1"
    text: str | None        # recognised text (None for non-OCR results)
    box: list[int]          # [x, y, w, h]
    score: float            # confidence 0-1

    @property
    def center(self) -> tuple[int, int]:
        """Return the centre point of the bounding box."""
        x, y, w, h = self.box
        return x + w // 2, y + h // 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ElementStore:
    """Manages the current set of Elements and persists them to disk.

    When *path* is ``None``, operates in memory-only mode (no file I/O).
    """

    def __init__(self, path: Path | None):
        self._path = path
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

    # ── lookup ──────────────────────────────────────────────────

    def resolve(self, ref_id: str) -> Element | None:
        """Find an Element by its short id (e.g. ``"e2"``)."""
        for e in self._elements:
            if e.ref == ref_id:
                return e
        return None

    # ── persistence ─────────────────────────────────────────────

    def save(self) -> None:
        """Write current elements to disk.  No-op if path is None (memory mode)."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elements": [e.to_dict() for e in self._elements],
        }
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> list[Element]:
        """Load elements from disk. Returns empty list if file missing or memory mode."""
        if self._path is None:
            return self._elements
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            # Support both old "refs" key and new "elements" key
            raw = data.get("elements") or data.get("refs", [])
            self._elements = [Element(**r) for r in raw]
            return self._elements
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            _log.warning("Failed to load elements from %s: %s", self._path, exc)
            return []

    @property
    def elements(self) -> list[Element]:
        return list(self._elements)
