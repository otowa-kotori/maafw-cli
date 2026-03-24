"""
Session management — Phase 1: file-based single session.

Stores connection parameters in ``~/.maafw/session.json`` so each CLI
invocation can reconnect to the same device.  TextRefs live in
``~/.maafw/textrefs.json``.

Phase 3 will replace this with a daemon + named sessions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir


# ── paths ──────────────────────────────────────────────────────

APP_NAME = "maafw-cli"
APP_AUTHOR = "MaaXYZ"


def _data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def session_file() -> Path:
    return _data_dir() / "session.json"


def textrefs_file() -> Path:
    return _data_dir() / "textrefs.json"


# ── session data ───────────────────────────────────────────────

@dataclass
class SessionInfo:
    """Serialisable connection parameters."""
    type: str              # "adb" or "win32"
    device: str            # device name / address
    adb_path: str = ""     # path to adb binary
    address: str = ""      # e.g. "127.0.0.1:5554"
    screencap_methods: int = 0
    input_methods: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    screenshot_short_side: int = 720

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionInfo":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def save_session(info: SessionInfo) -> None:
    """Persist session info to disk."""
    path = session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_session() -> Optional[SessionInfo]:
    """Load session info from disk.  Returns None if missing."""
    path = session_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionInfo.from_dict(data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None
