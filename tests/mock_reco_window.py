"""
Mock window for recognition integration tests.

Displays test fixture icons at known positions using absolute placement
so they are well-separated for TemplateMatch / FeatureMatch testing.

Layout (960x720):
    ┌─────────────────────────────────────────────┐
    │ [plus]                          [shapes]    │
    │                                             │
    │              [grid] (center)                │
    │                                             │
    │ [lenna_scaled]            [lenna_rotated]   │
    │                                             │
    │ [diamond_a]  [lenna]     [lenna_occluded]   │
    └─────────────────────────────────────────────┘

Usage:
    python tests/mock_reco_window.py <token>
"""
import sys
from pathlib import Path
import tkinter as tk

TOKEN = sys.argv[1] if len(sys.argv) > 1 else "reco_test"

root = tk.Tk()
root.title(f"MaafwReco_{TOKEN}")
root.geometry("960x720")
root.resizable(False, False)
root.configure(bg="#f0f0f0")

frame = tk.Frame(root, width=960, height=720, bg="#f0f0f0")
frame.pack_propagate(False)
frame.pack(fill="both", expand=True)

_fixtures_dir = Path(__file__).parent / "fixtures"
_images = []  # prevent GC


def _place_icon(name: str, x: int, y: int):
    """Place a fixture image at absolute (x, y) position."""
    path = _fixtures_dir / name
    if not path.exists():
        return
    img = tk.PhotoImage(file=str(path))
    _images.append(img)
    lbl = tk.Label(frame, image=img, bg="#f0f0f0", borderwidth=0)
    lbl.place(x=x, y=y)


# ── Top row ──
_place_icon("icon_plus.png",           20,   20)   # top-left
_place_icon("icon_shapes.png",        840,   20)   # top-right

# ── Center ──
_place_icon("icon_grid.png",          448,  300)   # center

# ── Lenna variants for FeatureMatch (well separated) ──
_place_icon("icon_lenna_scaled.png",   50,  350)   # left-middle  (192x192)
_place_icon("icon_lenna_rotated.png", 730,  350)   # right-middle (174x174)

# ── Bottom row ──
_place_icon("icon_diamond_a.png",      20,  640)   # bottom-left
_place_icon("icon_lenna.png",         416,  576)   # bottom-center (128x128)
_place_icon("icon_lenna_occluded.png", 800,  576)  # bottom-right

root.mainloop()
