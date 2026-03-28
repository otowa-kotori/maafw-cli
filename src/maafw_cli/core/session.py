"""
Session — unified per-session state container.

Each session owns an independent Resource instance (for template images and
pipeline definitions), an ElementStore, and an optional controller reference.
Multiple sessions do not pollute each other.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from maa.controller import Controller
from maa.resource import Resource
from maa.tasker import Tasker

from maafw_cli.core.errors import DeviceConnectionError
from maafw_cli.core.log import Timer
from maafw_cli.paths import get_resource_dir

_log = logging.getLogger("maafw_cli.core.session")


class Session:
    """Unified per-session state — owns controller, Resource, ElementStore."""

    def __init__(self, name: str = "default") -> None:
        self.name: str = name
        self.type: str = ""       # "adb" / "win32", set on attach
        self.device: str = ""     # device name, set on attach

        self._controller: Controller | None = None
        self._resource: Resource | None = None
        self._resource_lock = threading.Lock()
        self.lock: asyncio.Lock = asyncio.Lock()

        # Lazy import to avoid circular dependency
        from maafw_cli.core.element import ElementStore
        self.element_store: ElementStore = ElementStore()

    # ── controller ───────────────────────────────────────────────

    def attach(self, controller: Controller, type: str, device: str) -> None:
        """Bind (or replace) a controller and device metadata.

        If a previous controller exists and has a ``destroy`` method,
        it is called synchronously before replacement.
        """
        old_ctrl = self._controller
        if old_ctrl is not None and hasattr(old_ctrl, "destroy"):
            try:
                old_ctrl.destroy()
            except Exception:
                _log.warning(
                    "Error destroying old controller for session '%s'",
                    self.name, exc_info=True,
                )
        self._controller = controller
        self.type = type
        self.device = device
        _log.info(
            "Attached controller to session '%s' (type=%s, device=%s)",
            self.name, type, device,
        )

    @property
    def controller(self) -> Controller:
        """Return the controller.

        Raises :class:`DeviceConnectionError` if no controller is available.
        """
        if self._controller is None:
            raise DeviceConnectionError(
                f"Session '{self.name}' has no device connected."
            )
        return self._controller

    @property
    def has_controller(self) -> bool:
        """Check whether a controller is available."""
        return self._controller is not None

    # ── resource management ──────────────────────────────────────

    def get_resource(self) -> Resource | None:
        """Return the session's Resource, creating one on first call.

        Thread-safe.  Returns ``None`` if the OCR model bundle fails to load.
        """
        if self._resource is not None:
            return self._resource

        with self._resource_lock:
            if self._resource is not None:
                return self._resource

            resource_path = get_resource_dir()
            resource = Resource()

            if not resource.use_directml():
                _log.debug("DirectML not available, falling back to CPU inference")

            with Timer("resource bundle load", log=_log):
                if not resource.post_bundle(str(resource_path)).wait().succeeded:
                    return None

            self._resource = resource
            return resource

    def get_tasker(self) -> Tasker | None:
        """Create a Tasker bound to this session's controller and Resource."""
        resource = self.get_resource()
        if resource is None:
            return None
        tasker = Tasker()
        tasker.bind(resource, self.controller)
        if not tasker.inited:
            return None
        return tasker

    def load_image(self, path: str) -> bool:
        """Load image templates into this session's Resource."""
        resource = self.get_resource()
        if resource is None:
            return False
        with Timer("image resource load", log=_log):
            return resource.post_image(path).wait().succeeded

    def override_image(self, name: str, image: Any) -> bool:
        """Inject a numpy image into this session's Resource under *name*."""
        resource = self.get_resource()
        if resource is None:
            return False
        return resource.override_image(name, image)

    def load_pipeline(self, path: str) -> bool:
        """Load pipeline JSON/directory into this session's Resource."""
        from maafw_cli.core.errors import ActionError

        resource = self.get_resource()
        if resource is None:
            raise ActionError("Resource initialization failed.")
        with Timer("pipeline load", log=_log):
            return resource.post_pipeline(path).wait().succeeded

    def list_nodes(self) -> list[str]:
        """Return all node names currently loaded in this session's Resource."""
        from maafw_cli.core.errors import ActionError

        resource = self.get_resource()
        if resource is None:
            raise ActionError("Resource not initialized.")
        return resource.node_list

    def get_node_data(self, name: str) -> dict[str, Any] | None:
        """Return the JSON definition of a single node, or ``None``."""
        resource = self.get_resource()
        if resource is None:
            return None
        return resource.get_node_data(name)
