"""
``maafw-cli connect`` — establish device connections.
"""
from __future__ import annotations


import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_CONNECTION_ERROR
from maafw_cli.core.log import logger


@click.group()
def connect():
    """Connect to a device."""
    pass


@connect.command("adb")
@click.argument("device")
@click.option("--screenshot-size", type=int, default=720,
              help="Screenshot short-side resolution (default 720).")
@pass_ctx
def connect_adb(ctx: CliContext, device: str, screenshot_size: int) -> None:
    """Connect to an ADB device by name or address.

    DEVICE is the device name as shown by ``device list --adb``.
    """
    fmt = ctx.fmt
    logger.info("Connecting to ADB device '%s'…", device)

    # Initialise MaaFW toolkit
    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass

    from maafw_cli.maafw.adb import find_adb_devices, connect_adb as _connect

    # Find the requested device
    devices = find_adb_devices()
    match = None
    for d in devices:
        if d.name == device or d.address == device:
            match = d
            break

    if match is None:
        fmt.error(
            f"Device '{device}' not found. Available: {[d.name for d in devices]}",
            exit_code=EXIT_CONNECTION_ERROR,
        )

    # Connect
    controller = _connect(match, screenshot_short_side=screenshot_size)
    if controller is None:
        fmt.error(f"Failed to connect to '{device}'.", exit_code=EXIT_CONNECTION_ERROR)

    # Save session info for subsequent commands
    from maafw_cli.core.session import SessionInfo, save_session

    info = SessionInfo(
        type="adb",
        device=match.name,
        adb_path=match.adb_path,
        address=match.address,
        screencap_methods=match.screencap_methods,
        input_methods=match.input_methods,
        config=match.config,
        screenshot_short_side=screenshot_size,
    )
    save_session(info)

    fmt.success(
        {"session": "default", "type": "adb", "device": match.name, "address": match.address},
        human=f"Connected to {match.name} ({match.address})",
    )


_SCREENCAP_METHODS = {
    "GDI": "GDI",
    "FramePool": "FramePool",
    "DXGI_DesktopDup": "DXGI_DesktopDup",
    "DXGI_DesktopDup_Window": "DXGI_DesktopDup_Window",
    "PrintWindow": "PrintWindow",
    "ScreenDC": "ScreenDC",
}

_INPUT_METHODS = {
    "Seize": "Seize",
    "SendMessage": "SendMessage",
    "PostMessage": "PostMessage",
    "SendMessageWithCursorPos": "SendMessageWithCursorPos",
    "PostMessageWithCursorPos": "PostMessageWithCursorPos",
    "SendMessageWithWindowPos": "SendMessageWithWindowPos",
    "PostMessageWithWindowPos": "PostMessageWithWindowPos",
}


@connect.command("win32")
@click.argument("window")
@click.option("--screencap-method", type=click.Choice(list(_SCREENCAP_METHODS)),
              default="FramePool", show_default=True,
              help="Win32 screenshot method.")
@click.option("--input-method", type=click.Choice(list(_INPUT_METHODS)),
              default="PostMessage", show_default=True,
              help="Win32 input method.")
@pass_ctx
def connect_win32_cmd(ctx: CliContext, window: str,
                      screencap_method: str, input_method: str) -> None:
    """Connect to a Win32 window by title or hwnd (0x...).

    WINDOW is a window title substring (case-insensitive) or a hex hwnd
    like ``0x000A0B2C``.
    """
    fmt = ctx.fmt
    logger.info("Connecting to Win32 window '%s'…", window)

    # Initialise MaaFW toolkit
    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass

    from maafw_cli.maafw.win32 import find_win32_windows, connect_win32 as _connect

    windows = find_win32_windows()

    # Match by hwnd or title substring
    if window.startswith("0x") or window.startswith("0X"):
        # Exact hwnd match
        try:
            target_hwnd = int(window, 16)
        except ValueError:
            fmt.error(f"Invalid hwnd: '{window}'.", exit_code=EXIT_CONNECTION_ERROR)
            return  # unreachable — fmt.error exits

        matches = [w for w in windows if w.hwnd == target_hwnd]
    else:
        # Case-insensitive title substring match
        needle = window.lower()
        matches = [w for w in windows if needle in w.window_name.lower()]

    if not matches:
        fmt.error(
            f"No window matching '{window}'. Use 'device list --win32' to see available windows.",
            exit_code=EXIT_CONNECTION_ERROR,
        )

    if len(matches) > 1:
        listing = "\n".join(
            f"  {hex(m.hwnd):<14s} {m.window_name}" for m in matches
        )
        fmt.error(
            f"Multiple windows match '{window}'. Be more specific:\n{listing}",
            exit_code=EXIT_CONNECTION_ERROR,
        )

    matched = matches[0]

    # Connect
    from maa.define import MaaWin32ScreencapMethodEnum, MaaWin32InputMethodEnum

    sc_val = int(getattr(MaaWin32ScreencapMethodEnum, screencap_method))
    in_val = int(getattr(MaaWin32InputMethodEnum, input_method))

    controller = _connect(matched, screencap_method=sc_val, input_method=in_val)
    if controller is None:
        fmt.error(
            f"Failed to connect to '{matched.window_name}' ({hex(matched.hwnd)}).",
            exit_code=EXIT_CONNECTION_ERROR,
        )

    # Save session info for subsequent commands
    from maafw_cli.core.session import SessionInfo, save_session

    info = SessionInfo(
        type="win32",
        device=matched.window_name,
        address=hex(matched.hwnd),
        screencap_methods=sc_val,
        input_methods=in_val,
        window_name=matched.window_name,
    )
    save_session(info)

    fmt.success(
        {
            "session": "default",
            "type": "win32",
            "window_name": matched.window_name,
            "hwnd": hex(matched.hwnd),
            "class_name": matched.class_name,
        },
        human=f"Connected to {matched.window_name} ({hex(matched.hwnd)})",
    )
