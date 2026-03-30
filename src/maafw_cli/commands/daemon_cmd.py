"""
``daemon`` CLI commands — start / stop / restart / status.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext


@click.group("daemon")
def daemon_group():
    """Manage the background daemon."""
    pass


@daemon_group.command("start")
@click.option("--verbose", is_flag=True, default=False, help="Also log daemon output to stderr.")
@pass_ctx
def daemon_start(ctx: CliContext, verbose: bool) -> None:
    """Start the background daemon (if not already running)."""
    from maafw_cli.core.ipc import ensure_daemon

    fmt = ctx.fmt
    try:
        port = ensure_daemon()
        fmt.success({"status": "running", "port": port}, human=f"Daemon running on port {port}")
    except Exception as e:
        fmt.error(str(e), exit_code=3)


@daemon_group.command("stop")
@pass_ctx
def daemon_stop(ctx: CliContext) -> None:
    """Stop the background daemon."""
    from maafw_cli.core.ipc import DaemonClient, get_daemon_info

    fmt = ctx.fmt
    pid, port = get_daemon_info()
    if pid is None or port is None:
        fmt.success({"status": "not_running"}, human="Daemon is not running.")
        return

    try:
        client = DaemonClient(port)
        client.send("shutdown")
        fmt.success({"status": "shutdown_requested"}, human="Shutdown requested.")
    except Exception as e:
        fmt.error(f"Failed to stop daemon: {e}", exit_code=1)


@daemon_group.command("restart")
@click.option("--verbose", is_flag=True, default=False, help="Also log daemon output to stderr.")
@pass_ctx
def daemon_restart(ctx: CliContext, verbose: bool) -> None:
    """Restart the background daemon (stop then start)."""
    import time
    from maafw_cli.core.ipc import (
        DaemonClient, ensure_daemon, get_daemon_info, _is_process_alive,
    )

    fmt = ctx.fmt

    # Stop if running
    pid, port = get_daemon_info()
    if pid is not None and port is not None:
        try:
            client = DaemonClient(port)
            client.send("shutdown")
        except Exception:
            pass  # best effort

        # Wait for the process to exit (up to 5 seconds)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and _is_process_alive(pid):
            time.sleep(0.1)

    # Start
    try:
        new_port = ensure_daemon()
        fmt.success(
            {"status": "restarted", "port": new_port},
            human=f"Daemon restarted on port {new_port}",
        )
    except Exception as e:
        fmt.error(str(e), exit_code=3)


@daemon_group.command("status")
@pass_ctx
def daemon_status(ctx: CliContext) -> None:
    """Check daemon status."""
    from maafw_cli.core.ipc import DaemonClient, get_daemon_info

    fmt = ctx.fmt
    pid, port = get_daemon_info()

    if pid is None or port is None:
        fmt.success({"status": "not_running"}, human="Daemon is not running.")
        return

    try:
        client = DaemonClient(port)
        data = client.send("ping")
        uptime = data.get("uptime_seconds", 0)
        sessions = data.get("sessions", [])
        fmt.success(
            {"status": "running", "pid": pid, "port": port, "uptime": uptime, "sessions": sessions},
            human=(
                f"Daemon running — PID {pid}, port {port}, "
                f"uptime {uptime}s, {len(sessions)} session(s)"
            ),
        )
    except Exception as e:
        fmt.error(
            f"Daemon PID {pid} on port {port} is unreachable: {e}",
            exit_code=3,
        )
