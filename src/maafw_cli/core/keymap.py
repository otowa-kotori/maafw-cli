"""
Keymap tables and resolver for virtual key codes.

Supports both Windows VK codes and Android AKEYCODE, auto-selected
by session type.
"""
from __future__ import annotations

# ── Windows VK codes ─────────────────────────────────────────────

VK_MAP: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "escape": 0x1B, "esc": 0x1B,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "shift": 0x10, "ctrl": 0x11, "control": 0x11, "alt": 0x12,
    "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C,
    "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "printscreen": 0x2C, "pause": 0x13, "menu": 0x5D, "apps": 0x5D,
}

# ── Android AKEYCODE codes ───────────────────────────────────────

AK_MAP: dict[str, int] = {
    "enter": 66, "return": 66, "tab": 61, "space": 62,
    "backspace": 67, "delete": 112, "insert": 124,
    "escape": 111, "esc": 111,
    "up": 19, "down": 20, "left": 21, "right": 22,
    "home": 3, "end": 123, "pageup": 92, "pagedown": 93,
    "back": 4, "recent": 187, "appswitch": 187,
    "power": 26, "volume_up": 24, "volume_down": 25, "mute": 164,
    "camera": 27, "search": 84, "menu": 82, "wakeup": 224, "sleep": 223,
    "shift": 59, "ctrl": 113, "control": 113, "alt": 57,
    "capslock": 115, "numlock": 143, "scrolllock": 116,
    "f1": 131, "f2": 132, "f3": 133, "f4": 134,
    "f5": 135, "f6": 136, "f7": 137, "f8": 138,
    "f9": 139, "f10": 140, "f11": 141, "f12": 142,
    "printscreen": 120, "pause": 121,
}


# ── resolver ─────────────────────────────────────────────────────

def resolve_keycode(raw: str, session_type: str = "win32") -> int | None:
    """Return an integer keycode from a name, decimal, or 0x-hex string.

    Selects the keymap based on *session_type* (``"adb"`` or ``"win32"``).
    Raw integer input is passed through unchanged.
    """
    keymap = AK_MAP if session_type == "adb" else VK_MAP
    name = raw.strip().lower()
    if name in keymap:
        return keymap[name]
    try:
        return int(raw, 0)
    except ValueError:
        return None
