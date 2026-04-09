"""
Target parsing — resolve user-supplied click/action targets.

Supported formats:
- Element: ``e3``          → resolve from Element store → preserve full box
- Point:   ``452,387``     → literal point → ``(x, y, 0, 0)``
- Box:     ``10,20,30,40`` → literal box   → ``(x, y, w, h)``

Future:
- Text search: ``text:设置`` → auto-OCR → find → preserve full box
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from maafw_cli.core.element import ElementStore


@dataclass(frozen=True)
class ResolvedTarget:
    """The resolved box for a user-supplied target string."""

    box: tuple[int, int, int, int]
    source: str  # e.g. "ref:e3", "coords:452,387", "box:10,20,30,40"

    @property
    def center(self) -> tuple[int, int]:
        """Return the centre point of the resolved box."""
        x, y, w, h = self.box
        return x + w // 2, y + h // 2

    @property
    def x(self) -> int:
        """Backward-compatible centre X coordinate."""
        return self.center[0]

    @property
    def y(self) -> int:
        """Backward-compatible centre Y coordinate."""
        return self.center[1]


_REF_PATTERN = re.compile(r"^e(\d+)$", re.IGNORECASE)
_COORD_PATTERN = re.compile(r"^(-?\d+)\s*,\s*(-?\d+)$")
_BOX_PATTERN = re.compile(r"^(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)$")


def parse_target(target: str, store: ElementStore) -> Union[ResolvedTarget, str]:
    """Parse a target string and return a :class:`ResolvedTarget` or an error message."""

    target = target.strip()

    # 1. Try Element ref (e1, e2, …)
    m = _REF_PATTERN.match(target)
    if m:
        ref = store.resolve(target.lower())
        if ref is None:
            return f"Unknown reference '{target}'. Run 'maafw-cli ocr' or 'maafw-cli reco' first."
        return ResolvedTarget(
            box=tuple(int(v) for v in ref.box),
            source=f"ref:{ref.ref} \"{ref.text}\"",
        )

    # 2. Try literal box (x,y,w,h)
    m = _BOX_PATTERN.match(target)
    if m:
        return ResolvedTarget(
            box=tuple(int(m.group(i)) for i in range(1, 5)),
            source=f"box:{target}",
        )

    # 3. Try point coordinates (x,y)
    m = _COORD_PATTERN.match(target)
    if m:
        x = int(m.group(1))
        y = int(m.group(2))
        return ResolvedTarget(box=(x, y, 0, 0), source=f"coords:{target}")

    return (
        f"Cannot parse target '{target}'. Use e<N> (e.g. e3), x,y "
        f"(e.g. 452,387), or x,y,w,h (e.g. 10,20,30,40)."
    )
