"""
Daemon-specific logging configuration.

Writes to ``~/.maafw/daemon.log`` with rotation (5 MB × 3 backups).
Optionally mirrors to stderr for debugging (``--daemon-verbose``).
"""
from __future__ import annotations

import logging
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from maafw_cli.core.session import _data_dir


def daemon_log_path() -> Path:
    """Return the path to the daemon log file."""
    return _data_dir() / "daemon.log"


def setup_daemon_logging(*, verbose: bool = False) -> logging.Logger:
    """Configure and return the daemon logger.

    Parameters
    ----------
    verbose:
        If True, also output to stderr (useful for debugging).
    """
    log = logging.getLogger("maafw_cli.daemon")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()

    # ── file handler (always) ────────────────────────────────
    log_file = daemon_log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Truncate old log on each daemon start
    if log_file.exists():
        log_file.write_text("", encoding="utf-8")

    fh = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    log.addHandler(fh)

    # ── stderr handler (debug only) ──────────────────────────
    if verbose:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        ))
        log.addHandler(sh)

    # ── startup banner ───────────────────────────────────────
    log.info(
        "Daemon starting — PID=%d, Python=%s, platform=%s",
        __import__("os").getpid(),
        platform.python_version(),
        platform.platform(),
    )

    return log
