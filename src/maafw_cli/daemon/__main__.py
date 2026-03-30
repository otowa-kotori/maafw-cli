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
    parser.add_argument("--verbose", action="store_true", help="Also log to stderr.")
    args = parser.parse_args()

    # Set up daemon logging
    from maafw_cli.daemon.log import setup_daemon_logging
    setup_daemon_logging(verbose=args.verbose)

    # Populate the DISPATCH table — auto-import all service modules
    import importlib
    import pkgutil
    import maafw_cli.services as _svc_pkg
    for _info in pkgutil.iter_modules(_svc_pkg.__path__):
        importlib.import_module(f"maafw_cli.services.{_info.name}")

    from maafw_cli.daemon.server import DaemonServer

    server = DaemonServer(
        port=args.port,
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
