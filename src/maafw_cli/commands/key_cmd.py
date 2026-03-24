"""
``maafw-cli key`` — press a virtual key.

Automatically selects the correct keycode table based on the current
session type (ADB → Android AKEYCODE, Win32 → Windows VK).
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_ACTION_FAILED

# ── Windows VK codes ─────────────────────────────────────────────

VK_MAP: dict[str, int] = {
    # Editing / whitespace
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "escape": 0x1B,
    "esc": 0x1B,
    # Navigation
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    # Modifiers
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "lwin": 0x5B,
    "rwin": 0x5C,
    "capslock": 0x14,
    "numlock": 0x90,
    "scrolllock": 0x91,
    # Function keys
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    # Misc
    "printscreen": 0x2C,
    "pause": 0x13,
    "menu": 0x5D,
    "apps": 0x5D,
}

# ── Android AKEYCODE codes ───────────────────────────────────────
# https://developer.android.com/reference/android/view/KeyEvent

AK_MAP: dict[str, int] = {
    # Editing / whitespace
    "enter": 66,
    "return": 66,
    "tab": 61,
    "space": 62,
    "backspace": 67,   # AKEYCODE_DEL (backspace)
    "delete": 112,     # AKEYCODE_FORWARD_DEL
    "insert": 124,
    "escape": 111,
    "esc": 111,
    # Navigation
    "up": 19,
    "down": 20,
    "left": 21,
    "right": 22,
    "home": 3,         # AKEYCODE_HOME (Android Home button)
    "end": 123,        # AKEYCODE_MOVE_END
    "pageup": 92,
    "pagedown": 93,
    # Android-specific
    "back": 4,
    "recent": 187,     # AKEYCODE_APP_SWITCH
    "appswtich": 187,
    "power": 26,
    "volume_up": 24,
    "volume_down": 25,
    "mute": 164,
    "camera": 27,
    "search": 84,
    "menu": 82,
    "wakeup": 224,
    "sleep": 223,
    # Modifiers
    "shift": 59,       # AKEYCODE_SHIFT_LEFT
    "ctrl": 113,       # AKEYCODE_CTRL_LEFT
    "control": 113,
    "alt": 57,         # AKEYCODE_ALT_LEFT
    "capslock": 115,
    "numlock": 143,
    "scrolllock": 116,
    # Function keys
    "f1": 131,
    "f2": 132,
    "f3": 133,
    "f4": 134,
    "f5": 135,
    "f6": 136,
    "f7": 137,
    "f8": 138,
    "f9": 139,
    "f10": 140,
    "f11": 141,
    "f12": 142,
    # Misc
    "printscreen": 120,  # AKEYCODE_SYSRQ
    "pause": 121,        # AKEYCODE_BREAK
}


def resolve_keycode(raw: str, session_type: str = "win32") -> int | None:
    """Return an integer keycode from a name, decimal, or 0x-hex string.

    Selects the keymap based on *session_type* (``"adb"`` or ``"win32"``).
    Raw integer input is passed through unchanged.
    Returns ``None`` if the string cannot be resolved.
    """
    keymap = AK_MAP if session_type == "adb" else VK_MAP

    # Try named key (case-insensitive)
    name = raw.strip().lower()
    if name in keymap:
        return keymap[name]

    # Try integer literal (decimal or hex)
    try:
        return int(raw, 0)  # auto-detect base (0x prefix → hex)
    except ValueError:
        return None


@click.command("key")
@click.argument("keycode")
@pass_ctx
def key_cmd(ctx: CliContext, keycode: str) -> None:
    """Press a virtual key.

    KEYCODE can be a name (enter, tab, esc, back, f1-f12, ...) or an
    integer (decimal or 0x hex).  Named keys are automatically mapped
    to the correct code for the current session type (ADB or Win32).

    \b
    Examples:
      maafw-cli key enter       # ADB → 66, Win32 → 0x0D
      maafw-cli key back        # ADB → 4 (Android Back)
      maafw-cli key f5
      maafw-cli key 66          # raw integer, passed as-is
    """
    fmt = ctx.fmt

    # Determine session type for keymap selection
    from maafw_cli.core.session import load_session
    session = load_session()
    session_type = session.type if session else "win32"

    code = resolve_keycode(keycode, session_type)
    if code is None:
        platform = "Android" if session_type == "adb" else "Win32"
        fmt.error(
            f"Unknown key '{keycode}' for {platform}. "
            f"Use a name (enter, tab, back, f1, ...) or an integer.",
            exit_code=EXIT_ACTION_FAILED,
        )
        return  # unreachable — fmt.error exits

    fmt.info(f"Pressing key {keycode!r} → {code} (0x{code:02X}) [{session_type}]")

    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    from maafw_cli.maafw.control import press_key

    ok = press_key(controller, code)
    if not ok:
        fmt.error("Key press failed.", exit_code=EXIT_ACTION_FAILED)

    fmt.success(
        {
            "action": "key",
            "keycode": code,
            "keycode_hex": f"0x{code:02X}",
            "name": keycode,
            "session_type": session_type,
        },
        human=f"Pressed key {keycode} → {code} (0x{code:02X}) [{session_type}]",
    )
