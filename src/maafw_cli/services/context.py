"""
ServiceContext — runtime environment for service functions.

Encapsulates controller access, TextRef resolution, and session metadata
so that service functions stay free of infrastructure concerns.
"""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Callable

from maa.controller import Controller

from maafw_cli.core.errors import ActionError
from maafw_cli.core.target import parse_target, ResolvedTarget
from maafw_cli.core.textref import TextRefStore


class ServiceContext:
    """Injected into every service function as the first argument."""

    def __init__(
        self,
        get_controller: Callable[[], Controller],
        textrefs_path: Path | None,
        session_type: str = "win32",
        textref_store: TextRefStore | None = None,
        session_name: str | None = None,
    ):
        self._get_controller = get_controller
        self.textrefs_path = textrefs_path
        self.session_type = session_type  # "adb" or "win32"
        self._textref_store = textref_store  # injected store (daemon mode)
        self.session_name = session_name

    @cached_property
    def controller(self) -> Controller:
        """Lazy — first access triggers connection, then reuses."""
        return self._get_controller()

    def get_textref_store(self) -> TextRefStore:
        """Return the active TextRefStore (injected or file-based)."""
        if self._textref_store is not None:
            return self._textref_store
        store = TextRefStore(self.textrefs_path)
        store.load()
        return store

    def resolve_target(self, target: str) -> ResolvedTarget:
        """Parse t3 / 452,387 into (x, y).  Raises :class:`ActionError`."""
        store = self.get_textref_store()
        result = parse_target(target, store)
        if isinstance(result, str):
            raise ActionError(result)
        return result

    def invalidate_controller(self) -> None:
        """Force re-acquisition on next access (after connect)."""
        try:
            del self.__dict__["controller"]
        except KeyError:
            pass
