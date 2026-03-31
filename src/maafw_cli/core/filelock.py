"""
Cross-platform file lock — prevents concurrent daemon startup.

Uses ``fcntl.flock`` on POSIX and ``msvcrt.locking`` on Windows.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType


class FileLockError(OSError):
    """Raised when the file lock cannot be acquired (another process holds it)."""


class FileLock:
    """Non-blocking exclusive file lock as a context manager.

    Usage::

        try:
            with FileLock(path):
                # critical section
                ...
        except FileLockError:
            # another process holds the lock
            ...
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._fd: int | None = None

    def acquire(self) -> None:
        """Acquire the lock (non-blocking). Raises :class:`FileLockError` on failure."""
        import os

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)

        try:
            self._platform_lock(self._fd)
        except OSError:
            os.close(self._fd)
            self._fd = None
            raise FileLockError(
                f"Cannot acquire lock on {self.path} — another process holds it."
            )

    def release(self) -> None:
        """Release the lock."""
        import os

        if self._fd is not None:
            try:
                self._platform_unlock(self._fd)
            except OSError:
                pass
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()

    # ── platform-specific locking ──────────────────────────────────

    @staticmethod
    def _platform_lock(fd: int) -> None:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _platform_unlock(fd: int) -> None:
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
