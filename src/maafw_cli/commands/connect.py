"""
``maafw-cli connect`` — establish device connections.
"""
from __future__ import annotations


import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_CONNECTION_ERROR


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
    fmt.info(f"Connecting to ADB device '{device}'…")

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
