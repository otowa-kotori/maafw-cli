"""
Minimal Win32 test window using tkinter (stdlib, zero dependencies).

Launched as a subprocess by test_win32_manual.py.  Shows a window with:
- A unique title containing a random token (easy to locate via hwnd)
- A label showing "READY"
- A button; when clicked the label changes to "CLICKED"

This lets tests verify that SendMessage-based input actually works:
  1. Connect to the window
  2. OCR → see "READY"
  3. Click the button coordinates
  4. OCR → see "CLICKED"
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

root.mainloop()
