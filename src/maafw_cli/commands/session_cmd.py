"""
``session`` CLI commands — list / default / close.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext


@click.group("session")
def session_group():
    """Manage named daemon sessions."""
    pass


@session_group.command("list")
@pass_ctx
def session_list(ctx: CliContext) -> None:
    """List all active daemon sessions."""
    from maafw_cli.core.ipc import DaemonClient, ensure_daemon

    fmt = ctx.fmt
    try:
        port = ensure_daemon()
        client = DaemonClient(port)
        data = client.send("session_list")
        sessions = data.get("sessions", [])

        if fmt.json_mode:
            fmt.success(sessions)
        elif not sessions:
            fmt.success({"sessions": []}, human="No active sessions.")
        else:
            lines = []
            for s in sessions:
                marker = " *" if s.get("is_default") else "  "
                lines.append(f"{marker} {s['name']:<20s} {s['type']:<8s} {s['device']}")
            header = f"Sessions ({len(sessions)}):"
            fmt.success({"sessions": sessions}, human=header + "\n" + "\n".join(lines))
    except Exception as e:
        fmt.error(str(e), exit_code=1)


@session_group.command("default")
@click.argument("name")
@pass_ctx
def session_default(ctx: CliContext, name: str) -> None:
    """Set the default session."""
    from maafw_cli.core.ipc import DaemonClient, ensure_daemon

    fmt = ctx.fmt
    try:
        port = ensure_daemon()
        client = DaemonClient(port)
        client.send("session_default", {"name": name})
        fmt.success({"default": name}, human=f"Default session set to '{name}'.")
    except Exception as e:
        fmt.error(str(e), exit_code=1)


@session_group.command("close")
@click.argument("name")
@pass_ctx
def session_close(ctx: CliContext, name: str) -> None:
    """Close and destroy a named session."""
    from maafw_cli.core.ipc import DaemonClient, ensure_daemon

    fmt = ctx.fmt
    try:
        port = ensure_daemon()
        client = DaemonClient(port)
        client.send("session_close", {"name": name})
        fmt.success({"closed": name}, human=f"Session '{name}' closed.")
    except Exception as e:
        fmt.error(str(e), exit_code=1)
