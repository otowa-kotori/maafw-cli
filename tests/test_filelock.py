"""Tests for core/filelock.py — cross-platform file lock."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from maafw_cli.core.filelock import FileLock, FileLockError


class TestFileLock:
    def test_acquire_and_release(self, tmp_path: Path):
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock.acquire()
        assert lock._fd is not None
        lock.release()
        assert lock._fd is None

    def test_context_manager(self, tmp_path: Path):
        lock_path = tmp_path / "test.lock"
        with FileLock(lock_path) as lk:
            assert lk._fd is not None
        assert lk._fd is None

    def test_creates_parent_dirs(self, tmp_path: Path):
        lock_path = tmp_path / "sub" / "dir" / "test.lock"
        with FileLock(lock_path):
            assert lock_path.exists()

    def test_double_lock_fails(self, tmp_path: Path):
        """A second lock on the same file should raise FileLockError."""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock1.acquire()
        try:
            with pytest.raises(FileLockError):
                lock2 = FileLock(lock_path)
                lock2.acquire()
        finally:
            lock1.release()

    def test_lock_released_after_context(self, tmp_path: Path):
        """After exiting context, another lock should succeed."""
        lock_path = tmp_path / "test.lock"
        with FileLock(lock_path):
            pass
        # Should not raise
        with FileLock(lock_path):
            pass

    def test_concurrent_threads(self, tmp_path: Path):
        """Two threads competing for the same lock — one succeeds, one fails."""
        lock_path = tmp_path / "test.lock"
        results: list[str] = []
        barrier = threading.Barrier(2)

        def worker(name: str) -> None:
            barrier.wait()
            try:
                with FileLock(lock_path):
                    results.append(f"{name}:acquired")
                    # Hold lock briefly
                    import time
                    time.sleep(0.1)
            except FileLockError:
                results.append(f"{name}:failed")

        t1 = threading.Thread(target=worker, args=("A",))
        t2 = threading.Thread(target=worker, args=("B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # At least one should have acquired, at least one should have failed
        acquired = [r for r in results if "acquired" in r]
        failed = [r for r in results if "failed" in r]
        assert len(acquired) >= 1
        assert len(failed) >= 1
