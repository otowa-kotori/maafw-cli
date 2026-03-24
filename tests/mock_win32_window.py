"""
Minimal Win32 test window using tkinter (stdlib, zero dependencies).

Launched as a subprocess by test_win32_manual.py.  Shows a window with:
- A unique title containing a random token (easy to locate via hwnd)
- A label showing "READY"
- A button; when clicked the label changes to "CLICKED"
- Key press detection: pressing any key shows "KEY:<vk_code>" in the label
- Text input: an Entry widget that captures typed text
- Swipe detection: drag from one side to the other changes label to "SWIPED"

This lets tests verify that SendMessage-based input actually works:
  1. Connect to the window
  2. OCR -> see "READY"
  3. Click the button coordinates -> OCR sees "CLICKED"
  4. Press a key -> OCR sees "KEY:xx"
  5. Type text -> Entry widget shows the text
  6. Swipe -> OCR sees "SWIPED"
"""
import sys
import tkinter as tk

TOKEN = sys.argv[1] if len(sys.argv) > 1 else "maafw_test"

root = tk.Tk()
root.title(f"MaafwTest_{TOKEN}")
root.geometry("400x300")
root.resizable(False, False)

label = tk.Label(root, text="READY", font=("Arial", 48))
label.pack(expand=True, fill="both")


def on_click():
    label.config(text="CLICKED")


btn = tk.Button(root, text="PRESS", font=("Arial", 24), command=on_click)
btn.pack(fill="x", ipady=20)

# Entry for text input verification
entry = tk.Entry(root, font=("Arial", 18))
entry.pack(fill="x", padx=10, pady=5)
entry.focus_set()

# Key press detection on the root window
_drag_start = [None, None]


def on_key(event):
    label.config(text=f"KEY:{event.keycode}")


def on_mouse_down(event):
    _drag_start[0] = event.x
    _drag_start[1] = event.y


def on_mouse_up(event):
    if _drag_start[0] is not None:
        dx = event.x - _drag_start[0]
        dy = event.y - _drag_start[1]
        # If dragged more than 50px in any direction, count as swipe
        if abs(dx) > 50 or abs(dy) > 50:
            label.config(text="SWIPED")
    _drag_start[0] = None
    _drag_start[1] = None


root.bind("<Key>", on_key)
root.bind("<ButtonPress-1>", on_mouse_down)
root.bind("<ButtonRelease-1>", on_mouse_up)

root.mainloop()
