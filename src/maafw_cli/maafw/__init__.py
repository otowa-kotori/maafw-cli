"""
MaaFramework API thin wrappers.
"""
from __future__ import annotations


def init_toolkit() -> None:
    """Initialise MaaFramework toolkit (safe to call multiple times)."""
    try:
        from maa.toolkit import Toolkit
        from maafw_cli.paths import get_data_dir, ensure_dirs
        ensure_dirs()
        Toolkit.init_option(get_data_dir(), {"stdout_level": 0})
    except Exception:
        pass
