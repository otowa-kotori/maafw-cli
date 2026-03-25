"""
Cross-platform path management for maafw-cli.

Uses platformdirs for OS-appropriate data directories.
All data lives under ``MaaXYZ/maafw-cli`` (e.g. ``%LOCALAPPDATA%/MaaXYZ/maafw-cli``).
"""
from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "maafw-cli"
APP_AUTHOR = "MaaXYZ"


def get_data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def get_resource_dir() -> Path:
    return get_data_dir() / "resource"


def get_model_dir() -> Path:
    return get_resource_dir() / "model"


def get_ocr_dir() -> Path:
    return get_model_dir() / "ocr"


def get_screenshots_dir() -> Path:
    return get_data_dir() / "screenshots"


def ensure_dirs() -> None:
    """Ensure all necessary directories exist."""
    for d in [get_resource_dir(), get_model_dir(), get_ocr_dir(), get_screenshots_dir()]:
        d.mkdir(parents=True, exist_ok=True)
