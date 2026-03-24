"""
Structured exceptions for maafw-cli.

Service functions raise these instead of calling ``sys.exit``.
The CLI / REPL layer catches them and maps to exit codes or error messages.
"""
from __future__ import annotations


class MaafwError(Exception):
    """Base exception for all maafw-cli errors."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class ActionError(MaafwError):
    """An operation failed (exit code 1)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=1)


class RecognitionError(MaafwError):
    """Recognition / OCR failed (exit code 2)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=2)


class DeviceConnectionError(MaafwError):
    """Device / window connection failed (exit code 3)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=3)
