"""
Entry point: ``python -m maafw_cli.daemon``

Starts the daemon server in the foreground. Typically invoked by
``ensure_daemon()`` or ``maafw-cli daemon start``.
"""
from __future__ import annotations

import argparse
import asyncio
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="maafw-cli daemon")
    parser.add_argument("--port", type=int, default=None, help="Override TCP port.")
    parser.add_argument("--idle-timeout", type=int, default=300, help="Idle timeout in seconds.")
    parser.add_argument("--verbose", action="store_true", help="Also log to stderr.")
    args = parser.parse_args()

    # Set up daemon logging
    from maafw_cli.daemon.log import setup_daemon_logging
    setup_daemon_logging(verbose=args.verbose)

    # Populate the DISPATCH table with all service modules
    import maafw_cli.services.connection  # noqa: F401
    import maafw_cli.services.interaction  # noqa: F401
    import maafw_cli.services.vision  # noqa: F401
    import maafw_cli.services.resource  # noqa: F401

    from maafw_cli.daemon.server import DaemonServer

    server = DaemonServer(
        port=args.port,
        idle_timeout=args.idle_timeout,
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
