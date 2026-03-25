"""
Connection CLI commands — device adb/win32/all, connect adb, connect win32.

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


def _device_list(ctx: CliContext, *, adb_flag: bool, win32_flag: bool) -> None:
    """Shared implementation for device adb / win32 / all."""
    fmt = ctx.fmt

    try:
        result = ctx.run_raw(do_device_list, adb=adb_flag, win32=win32_flag)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if fmt.json_mode:
        fmt.success(result)
        return

    if adb_flag and "adb" in result:
        devices = result["adb"]
        if not devices:
            fmt.error("No ADB devices found.", exit_code=3)
            return
        lines = [f"  {d['name']:<30s} {d['address']}" for d in devices]
        fmt.success(devices, human=f"ADB devices ({len(devices)}):\n" + "\n".join(lines))

    if win32_flag and "win32" in result:
        windows = result["win32"]
        if not windows:
            fmt.error("No Win32 windows found.", exit_code=3)
            return
        lines = [f"  {w['hwnd']:<14s} {w['window_name']:<25s} {w['class_name']}" for w in windows]
        fmt.success(windows, human=f"Win32 windows ({len(windows)}):\n" + "\n".join(lines))


@device.command("adb")
@pass_ctx
def device_adb(ctx: CliContext) -> None:
    """List ADB devices."""
    _device_list(ctx, adb_flag=True, win32_flag=False)


@device.command("win32")
@pass_ctx
def device_win32(ctx: CliContext) -> None:
    """List Win32 windows."""
    _device_list(ctx, adb_flag=False, win32_flag=True)


@device.command("all")
@pass_ctx
def device_all(ctx: CliContext) -> None:
    """List both ADB devices and Win32 windows."""
    _device_list(ctx, adb_flag=True, win32_flag=True)


# ── connect ──────────────────────────────────────────────────────

@click.group()
def connect():
    """Connect to a device."""
    pass


@connect.command("adb")
@click.argument("device")
@click.option("--screenshot-size", type=int, default=720,
              help="Screenshot short-side resolution (default 720).")
@click.option("--as", "session_name", default=None,
              help="Name this session (default: device address).")
@pass_ctx
def connect_adb(ctx: CliContext, device: str, screenshot_size: int,
                session_name: str | None) -> None:
    """Connect to an ADB device by name or address.

    DEVICE is the device name as shown by ``device adb``.
    """
    name = session_name or device
    ctx.run(
        do_connect_adb,
        device=device,
        screenshot_size=screenshot_size,
        session_name=name,
    )


@connect.command("win32")
@click.argument("window")
@click.option("--screencap-method", type=click.Choice(SCREENCAP_METHODS),
              default="FramePool", show_default=True, help="Win32 screenshot method.")
@click.option("--input-method", type=click.Choice(INPUT_METHODS),
              default="PostMessage", show_default=True, help="Win32 input method.")
@click.option("--as", "session_name", default=None,
              help="Name this session (default: window title).")
@pass_ctx
def connect_win32_cmd(ctx: CliContext, window: str,
                      screencap_method: str, input_method: str,
                      session_name: str | None) -> None:
    """Connect to a Win32 window by title or hwnd (0x...).

    WINDOW is a window title substring (case-insensitive) or a hex hwnd
    like ``0x000A0B2C``.
    """
    name = session_name or window
    ctx.run(
        do_connect_win32,
        window=window,
        screencap_method=screencap_method,
        input_method=input_method,
        session_name=name,
    )
