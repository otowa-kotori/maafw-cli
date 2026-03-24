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
@pass_ctx
def device_list(ctx: CliContext, adb_flag: bool) -> None:
    """List available devices."""
    fmt = ctx.fmt

    if not adb_flag:
        # Default to ADB for Phase 1; Phase 2 adds --win32
        adb_flag = True

    if adb_flag:
        _list_adb(fmt)


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
