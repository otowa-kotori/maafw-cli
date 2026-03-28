"""
ServiceContext — runtime environment for service functions.

Wraps a :class:`Session` and provides Element resolution so that service
functions stay free of infrastructure concerns.
"""
from __future__ import annotations

from maafw_cli.core.errors import ActionError
from maafw_cli.core.session import Session
from maafw_cli.core.target import parse_target, ResolvedTarget
from maafw_cli.core.element import ElementStore

from maa.controller import Controller


class ServiceContext:
    """Injected into every service function as the first argument."""

    def __init__(self, session: Session):
        self.session = session

    @property
    def session_name(self) -> str:
        return self.session.name

    @property
    def session_type(self) -> str:
        return self.session.type

    @property
    def controller(self) -> Controller:
        """Delegate to session — raises if no device connected."""
        return self.session.controller

    def get_element_store(self) -> ElementStore:
        """Return the session's ElementStore."""
        return self.session.element_store

    def resolve_target(self, target: str) -> ResolvedTarget:
        """Parse e3 / 452,387 into (x, y).  Raises :class:`ActionError`."""
        store = self.get_element_store()
        result = parse_target(target, store)
        if isinstance(result, str):
            raise ActionError(result)
        return result
