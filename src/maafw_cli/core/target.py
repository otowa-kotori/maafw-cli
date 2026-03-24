"""
Target parsing — resolve user-supplied click/action targets.

Supported formats (Phase 1):
- TextRef:  ``t3``        → resolve from TextRef store → centre of bounding box
- Coords:   ``452,387``   → literal (x, y)

Phase 2 will add:
- Text search: ``text:设置``  → auto-OCR → find → centre
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from maafw_cli.core.textref import TextRefStore


@dataclass
class ResolvedTarget:
    """The result of parsing a target string."""
    x: int
    y: int
    source: str  # e.g. "ref:t3", "coords:452,387"


# Regex patterns
_REF_PATTERN = re.compile(r"^t(\d+)$", re.IGNORECASE)
_COORD_PATTERN = re.compile(r"^(\d+)\s*,\s*(\d+)$")


def parse_target(target: str, store: TextRefStore) -> Union[ResolvedTarget, str]:
    """Parse a target string and return a :class:`ResolvedTarget` or an error message."""

    target = target.strip()

    # 1. Try TextRef (t1, t2, …)
    m = _REF_PATTERN.match(target)
    if m:
        ref = store.resolve(target.lower())
        if ref is None:
            # Try loading from disk
            store.load()
            ref = store.resolve(target.lower())
        if ref is None:
            return f"Unknown reference '{target}'. Run 'maafw-cli ocr' first."
        cx, cy = ref.center
        return ResolvedTarget(x=cx, y=cy, source=f"ref:{ref.ref} \"{ref.text}\"")

    # 2. Try coordinates (x,y)
    m = _COORD_PATTERN.match(target)
    if m:
        return ResolvedTarget(x=int(m.group(1)), y=int(m.group(2)), source=f"coords:{target}")

    return f"Cannot parse target '{target}'. Use t<N> (e.g. t3) or x,y (e.g. 452,387)."
