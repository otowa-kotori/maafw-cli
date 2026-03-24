"""
Unified logging for maafw-cli.

Provides:
- ``setup_logging()`` to configure level / format based on --verbose / --quiet
- ``Timer`` context manager for timing blocks with automatic DEBUG output
- Module-level ``logger`` for general use

All log output goes to **stderr** so stdout remains a clean data channel.
"""
from __future__ import annotations

import logging
import sys
import time

logger = logging.getLogger("maafw_cli")


def setup_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    """Configure the root ``maafw_cli`` logger.

    Call once from the CLI entry point.

    +-----------+----------------+
    | Flag      | Level          |
    +-----------+----------------+
    | --quiet   | WARNING        |
    | (default) | INFO           |
    | --verbose | DEBUG          |
    +-----------+----------------+
    """
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)

    handler = logging.StreamHandler(sys.stderr)

    if verbose:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    else:
        # Default mode: bare messages, same look as the old fmt.info()
        handler.setFormatter(logging.Formatter("%(message)s"))

    logger.setLevel(level)
    logger.addHandler(handler)


class Timer:
    """Context manager that times a block and logs the result at DEBUG level.

    Usage::

        with Timer("screencap"):
            image = controller.post_screencap().wait().get()
        # -> DEBUG maafw_cli: screencap: 759ms

    The elapsed time is also available as ``timer.elapsed_ms`` after exit.
    """

    def __init__(self, label: str, *, log: logging.Logger | None = None):
        self.label = label
        self.elapsed_ms: int = 0
        self._log = log or logger
        self._t0: float = 0.0

    def __enter__(self) -> Timer:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.elapsed_ms = int((time.perf_counter() - self._t0) * 1000)
        self._log.debug("%s: %dms", self.label, self.elapsed_ms)
