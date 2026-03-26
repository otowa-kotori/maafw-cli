"""
Multi-stage mock window for pipeline integration tests.

Simulates a simple application with four screens/stages:
1. **Welcome** — Shows "WELCOME" label + "START" button
2. **Login**   — Shows "LOGIN" label + Username Entry + Password Entry + "SUBMIT" button
3. **Home**    — Shows "HOME" label + "SETTINGS" and "LOGOUT" buttons
4. **Settings**— Shows "SETTINGS" label + "BACK" button

A pipeline can automate the full flow:
  Click START → Type username → Type password → Click SUBMIT →
  Click SETTINGS → Click BACK → Click LOGOUT → back to Welcome

Each stage is a Frame that gets shown/hidden. The current stage label
is always large and prominent for OCR detection.

Usage:
    python tests/mock_pipeline_window.py <token>
"""
import sys
import tkinter as tk

TOKEN = sys.argv[1] if len(sys.argv) > 1 else "pipeline_test"

root = tk.Tk()
root.title(f"MaafwPipeline_{TOKEN}")
root.geometry("960x720")
root.resizable(False, False)
root.configure(bg="white")


# ── Stage management ────────────────────────────────────────────

_frames: dict[str, tk.Frame] = {}
_current_stage = "welcome"


def _show_stage(name: str):
    global _current_stage
    for key, frame in _frames.items():
        if key == name:
            frame.pack(fill="both", expand=True)
        else:
            frame.pack_forget()
    _current_stage = name


# ── Stage 1: Welcome ────────────────────────────────────────────

welcome = tk.Frame(root, bg="white")
_frames["welcome"] = welcome

tk.Label(welcome, text="WELCOME", font=("Arial", 56, "bold"), bg="white").pack(
    pady=(120, 40)
)
tk.Label(welcome, text="Pipeline Demo App", font=("Arial", 20), bg="white", fg="gray").pack(
    pady=10
)
tk.Button(
    welcome,
    text="START",
    font=("Arial", 28),
    width=12,
    command=lambda: _show_stage("login"),
).pack(pady=40)


# ── Stage 2: Login ──────────────────────────────────────────────

login = tk.Frame(root, bg="white")
_frames["login"] = login

tk.Label(login, text="LOGIN", font=("Arial", 56, "bold"), bg="white").pack(
    pady=(80, 30)
)

login_form = tk.Frame(login, bg="white")
login_form.pack(pady=10)

tk.Label(login_form, text="Username:", font=("Arial", 18), bg="white").grid(
    row=0, column=0, padx=10, pady=10, sticky="e"
)
username_entry = tk.Entry(login_form, font=("Arial", 18), width=20)
username_entry.grid(row=0, column=1, padx=10, pady=10)

tk.Label(login_form, text="Password:", font=("Arial", 18), bg="white").grid(
    row=1, column=0, padx=10, pady=10, sticky="e"
)
password_entry = tk.Entry(login_form, font=("Arial", 18), width=20, show="*")
password_entry.grid(row=1, column=1, padx=10, pady=10)

# Status label for login feedback
login_status = tk.Label(login, text="", font=("Arial", 14), bg="white", fg="red")
login_status.pack(pady=5)


def _do_login():
    user = username_entry.get().strip()
    pwd = password_entry.get().strip()
    if user and pwd:
        _show_stage("home")
    else:
        login_status.config(text="INVALID")


tk.Button(
    login,
    text="SUBMIT",
    font=("Arial", 24),
    width=12,
    command=_do_login,
).pack(pady=20)


# ── Stage 3: Home ──────────────────────────────────────────────

home = tk.Frame(root, bg="white")
_frames["home"] = home

tk.Label(home, text="HOME", font=("Arial", 56, "bold"), bg="white").pack(
    pady=(120, 40)
)
tk.Label(home, text="Welcome back!", font=("Arial", 20), bg="white", fg="gray").pack(
    pady=10
)

home_buttons = tk.Frame(home, bg="white")
home_buttons.pack(pady=30)

tk.Button(
    home_buttons,
    text="SETTINGS",
    font=("Arial", 22),
    width=12,
    command=lambda: _show_stage("settings"),
).pack(side="left", padx=20)

tk.Button(
    home_buttons,
    text="LOGOUT",
    font=("Arial", 22),
    width=12,
    command=lambda: _show_stage("complete"),
).pack(side="left", padx=20)


# ── Stage 4: Settings ──────────────────────────────────────────

settings = tk.Frame(root, bg="white")
_frames["settings"] = settings

tk.Label(settings, text="SETTINGS", font=("Arial", 56, "bold"), bg="white").pack(
    pady=(120, 40)
)
tk.Label(settings, text="Nothing to configure.", font=("Arial", 20), bg="white", fg="gray").pack(
    pady=10
)
tk.Button(
    settings,
    text="BACK",
    font=("Arial", 24),
    width=12,
    command=lambda: _show_stage("home"),
).pack(pady=40)


# ── Stage 5: Complete ──────────────────────────────────────────

complete = tk.Frame(root, bg="white")
_frames["complete"] = complete

tk.Label(complete, text="COMPLETE", font=("Arial", 56, "bold"), bg="white").pack(
    pady=(200, 40)
)
tk.Label(complete, text="Pipeline finished successfully.", font=("Arial", 20), bg="white", fg="gray").pack(
    pady=10
)


# ── Start ──────────────────────────────────────────────────────

_show_stage("welcome")
root.mainloop()
