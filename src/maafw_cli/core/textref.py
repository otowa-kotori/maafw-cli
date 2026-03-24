"""
TextRef system — short references (t1, t2, …) for OCR results.

Each OCR run assigns sequential refs. Refs are persisted to
``~/.maafw/textrefs.json`` so later commands (e.g. ``click t2``)
can resolve them without re-running OCR.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from maa.define import OCRResult


@dataclass
class TextRef:
    """A single OCR result with a short reference id."""
    ref: str          # e.g. "t1"
    text: str         # recognised text
    box: list[int]    # [x, y, w, h]
    score: float      # confidence 0-1

    @property
    def center(self) -> tuple[int, int]:
        """Return the centre point of the bounding box."""
        x, y, w, h = self.box
        return x + w // 2, y + h // 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextRefStore:
    """Manages the current set of TextRefs and persists them to disk."""

    def __init__(self, path: Path):
        self._path = path
        self._refs: list[TextRef] = []

    # ── building ────────────────────────────────────────────────

    def build_from_ocr(self, ocr_results: list[OCRResult]) -> list[TextRef]:
        """Convert MaaFW ``OCRResult`` objects into numbered TextRefs."""
        refs: list[TextRef] = []
        for i, r in enumerate(ocr_results, start=1):
            box = list(r.box) if isinstance(r.box, (list, tuple)) else [0, 0, 0, 0]
            ref = TextRef(
                ref=f"t{i}",
                text=str(r.text),
                box=[int(v) for v in box],
                score=round(float(r.score), 4),
            )
            refs.append(ref)
        self._refs = refs
        return refs

    # ── lookup ──────────────────────────────────────────────────

    def resolve(self, ref_id: str) -> TextRef | None:
        """Find a TextRef by its short id (e.g. ``"t2"``)."""
        for r in self._refs:
            if r.ref == ref_id:
                return r
        return None

    # ── persistence ─────────────────────────────────────────────

    def save(self) -> None:
        """Write current refs to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now().isoformat(),
            "refs": [r.to_dict() for r in self._refs],
        }
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> list[TextRef]:
        """Load refs from disk. Returns empty list if file missing."""
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._refs = [TextRef(**r) for r in data.get("refs", [])]
            return self._refs
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    @property
    def refs(self) -> list[TextRef]:
        return list(self._refs)
