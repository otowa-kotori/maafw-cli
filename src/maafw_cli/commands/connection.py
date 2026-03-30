"""
Connection CLI commands — device adb/win32/all, connect adb, connect win32.

Thin shells over ``services.connection``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.services.connection import do_connect_adb, do_connect_win32, do_device_list


# ── device ───────────────────────────────────────────────────────

@click.group()
def device():
    """Discover available devices."""
    pass


def _device_list(ctx: CliContext, *, adb_flag: bool, win32_flag: bool, filter: str | None = None) -> None:
    """Shared implementation for device adb / win32 / all."""
    fmt = ctx.fmt

    try:
        result = ctx.run_raw(do_device_list, adb=adb_flag, win32=win32_flag, filter=filter)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if fmt.json_mode:
        fmt.success(result)
        return

    both = adb_flag and win32_flag  # "device all" mode

    adb_devices = result.get("adb", []) if adb_flag else []
    win32_windows = result.get("win32", []) if win32_flag else []

    # In "all" mode, only fail when both sides are empty
    if both and not adb_devices and not win32_windows:
        fmt.error("No devices found.", exit_code=3)
        return

    # In single-source mode, fail when that source is empty
    if not both:
        if adb_flag and not adb_devices:
            fmt.error("No ADB devices found.", exit_code=3)
            return
        if win32_flag and not win32_windows:
            fmt.error("No Win32 windows found.", exit_code=3)
            return

    if adb_devices:
        lines = [f"  {d['name']:<30s} {d['address']}" for d in adb_devices]
        fmt.success(adb_devices, human=f"ADB devices ({len(adb_devices)}):\n" + "\n".join(lines))

    if win32_windows:
        lines = [f"  {w['hwnd']:<14s} {w['window_name']:<25s} {w['class_name']}" for w in win32_windows]
        fmt.success(win32_windows, human=f"Win32 windows ({len(win32_windows)}):\n" + "\n".join(lines))


@device.command("adb")
@click.argument("filter", required=False, default=None)
@pass_ctx
def device_adb(ctx: CliContext, filter: str | None) -> None:
    """List ADB devices. Optionally filter by name or address substring."""
    _device_list(ctx, adb_flag=True, win32_flag=False, filter=filter)


@device.command("win32")
@click.argument("filter", required=False, default=None)
@pass_ctx
def device_win32(ctx: CliContext, filter: str | None) -> None:
    """List Win32 windows. Optionally filter by window name or class name substring."""
    _device_list(ctx, adb_flag=False, win32_flag=True, filter=filter)


@device.command("all")
@click.argument("filter", required=False, default=None)
@pass_ctx
def device_all(ctx: CliContext, filter: str | None) -> None:
    """List both ADB devices and Win32 windows. Optionally filter by name substring."""
    _device_list(ctx, adb_flag=True, win32_flag=True, filter=filter)


# ── connect ──────────────────────────────────────────────────────

@click.group()
def connect():
    """Connect to a device."""
    pass


@connect.command("adb")
@click.argument("device")
@click.option("--size", type=str, default="short:720", show_default=True,
              help="Screenshot resolution: 'short:<px>' (short-side), 'long:<px>' (long-side), or 'raw' (no scaling).")
@click.option("--screencap-method", type=str, default=None,
              help="ADB screenshot method (comma-separated for fallback, e.g. Default). "
                   "Uses device-reported default when omitted.")
@click.option("--input-method", type=str, default=None,
              help="ADB input method (comma-separated for fallback, e.g. Default). "
                   "Uses device-reported default when omitted.")
@pass_ctx
def connect_adb(ctx: CliContext, device: str, size: str,
                screencap_method: str | None, input_method: str | None) -> None:
    """Connect to an ADB device by name or address.

    DEVICE is the device name as shown by ``device adb``.
    Use global ``--on NAME`` to assign a session name (default: 'default').
    """
    name = ctx.on or "default"
    ctx.run(
        do_connect_adb,
        device=device,
        size=size,
        screencap_method=screencap_method,
        input_method=input_method,
        session_name=name,
    )


@connect.command("win32")
@click.argument("window")
@click.option("--size", type=str, default="short:720", show_default=True,
              help="Screenshot resolution: 'raw' (no scaling), 'short:<px>' (short-side), or 'long:<px>' (long-side).")
@click.option("--screencap-method", type=str,
              default="FramePool", show_default=True,
              help="Win32 screenshot method (comma-separated for fallback, e.g. FramePool,PrintWindow).")
@click.option("--input-method", type=str,
              default="PostMessage", show_default=True,
              help="Win32 input method (comma-separated for fallback, e.g. PostMessage,Seize).")
@pass_ctx
def connect_win32_cmd(ctx: CliContext, window: str, size: str,
                      screencap_method: str, input_method: str) -> None:
    """Connect to a Win32 window by title or hwnd (0x...).

    WINDOW is a window title substring (case-insensitive) or a hex hwnd
    like ``0x000A0B2C``.
    Use global ``--on NAME`` to assign a session name (default: 'default').
    """
    name = ctx.on or "default"
    ctx.run(
        do_connect_win32,
        window=window,
        screencap_method=screencap_method,
        input_method=input_method,
        size=size,
        session_name=name,
    )
