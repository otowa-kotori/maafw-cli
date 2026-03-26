"""
Mock clicking game window for pipeline integration tests.

A timed clicking game with three screens:
1. **Start**     -- "CLICKING GAME" title + "PLAY" button
2. **Game**      -- Target icon hint + 3 icon buttons (randomized) + timer + score
3. **Game Over** -- "GAME OVER" + "Score: N"

The game shows a target icon in the hint area and the player must click the
matching icon button in the game area.  Correct clicks score +1, wrong clicks
score -1.  After the timer expires, the game ends automatically.

Icons are loaded from ``tests/fixtures/game_{apple,lemon,grape}.png`` (RGBA)
via ``tk.PhotoImage``.  Pipeline uses ``game_{name}_mask.png`` (green-mask
templates) with ``green_mask=true`` for TemplateMatch recognition.

The hint area has a light-gray background and each button slot has a randomly
tinted/patterned background to prove that green_mask correctly ignores the
background when matching.

Layout (960x720):
    y=0-60    [Time: 20s]              [Score: 0]   <- top bar (OCR)
    y=60-180  [ "Click:" ] [target icon]             <- hint area
    y=250+    [  icon1  ]  [  icon2  ]  [  icon3  ]  <- game area

Usage:
    python tests/mock_clicking_game.py <token>
"""
import random
import sys
import tkinter as tk
from pathlib import Path

TOKEN = sys.argv[1] if len(sys.argv) > 1 else "game_test"

GAME_DURATION = 20  # seconds
ICON_NAMES = ["apple", "lemon", "grape"]

# Distinct pastel/tinted background colors for button slots.
# These are deliberately different from each other AND from white/gray
# so that green_mask is truly needed for reliable TemplateMatch.
_SLOT_COLORS = ["#e8d0d0", "#d0e8d0", "#d0d0e8"]  # pinkish, greenish, bluish

_fixtures_dir = Path(__file__).parent / "fixtures"

root = tk.Tk()
root.title(f"MaafwGame_{TOKEN}")
root.geometry("960x720")
root.resizable(False, False)
root.configure(bg="white")

# ── Load icon images ──────────────────────────────────────────

_images: dict[str, tk.PhotoImage] = {}
for name in ICON_NAMES:
    path = _fixtures_dir / f"game_{name}.png"
    if path.exists():
        _images[name] = tk.PhotoImage(file=str(path))

# ── Frame management ──────────────────────────────────────────

_frames: dict[str, tk.Frame] = {}


def _show_frame(name: str):
    for key, frame in _frames.items():
        if key == name:
            frame.pack(fill="both", expand=True)
        else:
            frame.pack_forget()


# ── Screen 1: Start ──────────────────────────────────────────

start_frame = tk.Frame(root, bg="white")
_frames["start"] = start_frame

tk.Label(
    start_frame, text="CLICKING GAME",
    font=("Arial", 48, "bold"), bg="white",
).pack(pady=(180, 40))

tk.Button(
    start_frame, text="PLAY",
    font=("Arial", 32, "bold"), width=10,
    command=lambda: _start_game(),
).pack(pady=30)


# ── Screen 2: Game ────────────────────────────────────────────

game_frame = tk.Frame(root, bg="white", width=960, height=720)
_frames["game"] = game_frame

# Top bar
top_bar = tk.Frame(game_frame, bg="white", height=60)
top_bar.pack(fill="x", pady=(0, 0))
top_bar.pack_propagate(False)

time_label = tk.Label(
    top_bar, text="Time: 20",
    font=("Arial", 28, "bold"), bg="white", fg="black",
)
time_label.pack(side="left", padx=40, pady=10)

score_label = tk.Label(
    top_bar, text="Score: 0",
    font=("Arial", 28, "bold"), bg="white", fg="black",
)
score_label.pack(side="right", padx=40, pady=10)

# Hint area (y ~ 60-180) — light gray background (different from button areas)
hint_area = tk.Frame(game_frame, bg="#e0e0e0", height=120)
hint_area.pack(fill="x", padx=150, pady=(10, 20))
hint_area.pack_propagate(False)

hint_text = tk.Label(
    hint_area, text="Click:",
    font=("Arial", 24), bg="#e0e0e0",
)
hint_text.pack(side="left", padx=(40, 20), pady=10)

hint_icon_label = tk.Label(hint_area, bg="#e0e0e0", borderwidth=0)
hint_icon_label.pack(side="left", padx=20, pady=10)

# Spacer
tk.Frame(game_frame, bg="white", height=40).pack()

# Game area (y ~ 250+)
game_area = tk.Frame(game_frame, bg="white", height=300)
game_area.pack(fill="x", pady=(10, 0))
game_area.pack_propagate(False)

# Three button slots — each has a DIFFERENT tinted background
_btn_frames: list[tk.Frame] = []
_btn_labels: list[tk.Label] = []
_btn_icons: list[str] = ["", "", ""]  # track which icon is in which slot

for i in range(3):
    bg_color = _SLOT_COLORS[i]
    slot = tk.Frame(game_area, bg=bg_color, width=200, height=200)
    slot.pack(side="left", expand=True, padx=30, pady=20)
    slot.pack_propagate(False)
    _btn_frames.append(slot)

    lbl = tk.Label(
        slot, bg=bg_color, borderwidth=2, relief="raised",
        cursor="hand2",
    )
    lbl.pack(expand=True, fill="both", padx=10, pady=10)
    lbl.bind("<Button-1>", lambda e, idx=i: _on_icon_click(idx))
    _btn_labels.append(lbl)


# ── Screen 3: Game Over ──────────────────────────────────────

gameover_frame = tk.Frame(root, bg="white")
_frames["gameover"] = gameover_frame

gameover_title = tk.Label(
    gameover_frame, text="GAME OVER",
    font=("Arial", 56, "bold"), bg="white",
)
gameover_title.pack(pady=(200, 40))

gameover_score = tk.Label(
    gameover_frame, text="Score: 0",
    font=("Arial", 36, "bold"), bg="white", fg="blue",
)
gameover_score.pack(pady=20)

gameover_misses = tk.Label(
    gameover_frame, text="Misses: 0",
    font=("Arial", 28), bg="white", fg="red",
)
gameover_misses.pack(pady=10)


# ── Game logic ────────────────────────────────────────────────

_score = 0
_misses = 0  # wrong clicks counter
_time_left = GAME_DURATION
_target: str = ""  # current target icon name
_timer_id: str | None = None


def _start_game():
    global _score, _misses, _time_left
    _score = 0
    _misses = 0
    _time_left = GAME_DURATION
    score_label.config(text=f"Score: {_score}")
    time_label.config(text=f"Time: {_time_left}")
    _show_frame("game")
    _new_round()
    _tick()


def _new_round():
    """Set up a new round: pick a target and randomize button order."""
    global _target
    _target = random.choice(ICON_NAMES)

    # Update hint icon
    if _target in _images:
        hint_icon_label.config(image=_images[_target])
    else:
        hint_icon_label.config(text=_target)

    # Randomize button order
    order = ICON_NAMES[:]
    random.shuffle(order)
    for i, name in enumerate(order):
        _btn_icons[i] = name
        if name in _images:
            _btn_labels[i].config(image=_images[name])
        else:
            _btn_labels[i].config(text=name)


def _on_icon_click(idx: int):
    global _score, _misses
    clicked = _btn_icons[idx]
    if clicked == _target:
        _score += 1
        score_label.config(text=f"Score: {_score}")
        _new_round()
    else:
        _score -= 1
        _misses += 1
        score_label.config(text=f"Score: {_score}")
        # Don't refresh layout on wrong click


def _tick():
    global _time_left, _timer_id
    _time_left -= 1
    time_label.config(text=f"Time: {_time_left}")
    if _time_left <= 0:
        _end_game()
    else:
        _timer_id = root.after(1000, _tick)


def _end_game():
    global _timer_id
    if _timer_id is not None:
        root.after_cancel(_timer_id)
        _timer_id = None
    gameover_score.config(text=f"Score: {_score}")
    gameover_misses.config(text=f"Misses: {_misses}")
    _show_frame("gameover")


# ── Launch ────────────────────────────────────────────────────

_show_frame("start")
root.mainloop()
