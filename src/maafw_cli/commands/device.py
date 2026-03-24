"""
``maafw-cli device`` — device discovery commands.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext


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
        # Default to ADB for backward compatibility
        adb_flag = True

    if adb_flag:
        _list_adb(fmt)

    if win32_flag:
        _list_win32(fmt)


def _list_adb(fmt) -> None:
    from maafw_cli.maafw.adb import find_adb_devices

    fmt.info("Scanning ADB devices…")

    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass

    devices = find_adb_devices()
    if not devices:
        fmt.error("No ADB devices found.", exit_code=3)

    if fmt.json_mode:
        fmt.success([
            {"name": d.name, "address": d.address, "adb_path": d.adb_path}
            for d in devices
        ])
    else:
        lines = []
        for d in devices:
            lines.append(f"  {d.name:<30s} {d.address}")
        header = f"ADB devices ({len(devices)}):"
        fmt.success(
            [{"name": d.name, "address": d.address} for d in devices],
            human=header + "\n" + "\n".join(lines),
        )


def _list_win32(fmt) -> None:
    from maafw_cli.maafw.win32 import find_win32_windows

    fmt.info("Scanning Win32 windows…")

    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass

    windows = find_win32_windows()
    if not windows:
        fmt.error("No Win32 windows found.", exit_code=3)

    if fmt.json_mode:
        fmt.success([
            {"hwnd": hex(w.hwnd), "window_name": w.window_name, "class_name": w.class_name}
            for w in windows
        ])
    else:
        lines = []
        for w in windows:
            lines.append(f"  {hex(w.hwnd):<14s} {w.window_name:<25s} {w.class_name}")
        header = f"Win32 windows ({len(windows)}):"
        fmt.success(
            [{"hwnd": hex(w.hwnd), "window_name": w.window_name, "class_name": w.class_name}
             for w in windows],
            human=header + "\n" + "\n".join(lines),
        )
