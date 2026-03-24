"""
Connection CLI commands — device list, connect adb, connect win32.

Thin shells over ``services.connection``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.keymap import SCREENCAP_METHODS, INPUT_METHODS
from maafw_cli.services.connection import do_connect_adb, do_connect_win32, do_device_list


# ── device ───────────────────────────────────────────────────────

@click.group()
def device():
    """Discover available devices."""
    pass


@device.command("list")
@click.option("--adb", "adb_flag", is_flag=True, default=False, help="Scan for ADB devices.")
@click.option("--win32", "win32_flag", is_flag=True, default=False, help="List Win32 windows.")
@pass_ctx
def device_list(ctx: CliContext, adb_flag: bool, win32_flag: bool) -> None:
    """List available devices."""
    fmt = ctx.fmt

    if not adb_flag and not win32_flag:
        adb_flag = True

    try:
        result = do_device_list(adb=adb_flag, win32=win32_flag)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if adb_flag and "adb" in result:
        devices = result["adb"]
        if not devices:
            fmt.error("No ADB devices found.", exit_code=3)
        if fmt.json_mode:
            fmt.success(devices)
        else:
            lines = [f"  {d['name']:<30s} {d['address']}" for d in devices]
            fmt.success(devices, human=f"ADB devices ({len(devices)}):\n" + "\n".join(lines))

    if win32_flag and "win32" in result:
        windows = result["win32"]
        if not windows:
            fmt.error("No Win32 windows found.", exit_code=3)
        if fmt.json_mode:
            fmt.success(windows)
        else:
            lines = [f"  {w['hwnd']:<14s} {w['window_name']:<25s} {w['class_name']}" for w in windows]
            fmt.success(windows, human=f"Win32 windows ({len(windows)}):\n" + "\n".join(lines))


# ── connect ──────────────────────────────────────────────────────

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
    try:
        result = do_connect_adb(device, screenshot_size=screenshot_size)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return
    fmt.success(result, human=f"Connected to {result['device']} ({result['address']})")


@connect.command("win32")
@click.argument("window")
@click.option("--screencap-method", type=click.Choice(SCREENCAP_METHODS),
              default="FramePool", show_default=True, help="Win32 screenshot method.")
@click.option("--input-method", type=click.Choice(INPUT_METHODS),
              default="PostMessage", show_default=True, help="Win32 input method.")
@pass_ctx
def connect_win32_cmd(ctx: CliContext, window: str,
                      screencap_method: str, input_method: str) -> None:
    """Connect to a Win32 window by title or hwnd (0x...).

    WINDOW is a window title substring (case-insensitive) or a hex hwnd
    like ``0x000A0B2C``.
    """
    fmt = ctx.fmt
    try:
        result = do_connect_win32(window, screencap_method=screencap_method, input_method=input_method)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return
    fmt.success(result, human=f"Connected to {result['window_name']} ({result['hwnd']})")
