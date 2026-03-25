"""
JSON-line protocol for daemon ↔ client IPC.

Each message is a single JSON object terminated by ``\\n``.
Shared by both client and server.
"""
from __future__ import annotations

import json
import uuid
from typing import Any


# ── encode / decode ─────────────────────────────────────────────

def encode(msg: dict[str, Any]) -> bytes:
    """Serialize a message dict to a JSON-line (bytes, newline-terminated)."""
    return json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    """Deserialize a JSON-line (bytes) back to a dict.

    Raises :class:`ValueError` on malformed input.
    """
    text = line.strip()
    if not text:
        raise ValueError("Empty line")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object, got {type(obj).__name__}")
    return obj


# ── request helpers ─────────────────────────────────────────────

def make_request(
    action: str,
    params: dict[str, Any] | None = None,
    *,
    session: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a request dict ready for :func:`encode`."""
    return {
        "id": request_id or uuid.uuid4().hex[:16],
        "action": action,
        "session": session,
        "params": params or {},
    }


# ── response helpers ────────────────────────────────────────────

def ok_response(request_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a success response."""
    return {
        "id": request_id,
        "ok": True,
        "data": data or {},
    }


def error_response(
    request_id: str,
    error: str,
    exit_code: int = 1,
) -> dict[str, Any]:
    """Build an error response."""
    return {
        "id": request_id,
        "ok": False,
        "error": error,
        "exit_code": exit_code,
    }
