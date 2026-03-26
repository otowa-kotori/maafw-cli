"""
Pipeline operations — load, run, list, get, validate via MaaFramework.

Reuses the cached Resource from ``vision.py`` for the OCR model bundle,
and provides pipeline-specific wrappers around ``Resource.post_pipeline()``,
``Tasker.post_task()``, etc.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from maa.controller import Controller
from maa.resource import Resource
from maa.tasker import Tasker, TaskDetail

from maafw_cli.core.errors import ActionError
from maafw_cli.core.log import Timer
from maafw_cli.maafw.vision import _get_resource, _get_tasker

_log = logging.getLogger("maafw_cli.maafw.pipeline")


def load_pipeline(path: str | Path) -> bool:
    """Load pipeline JSON/directory into the cached Resource.

    *path* can be a directory containing pipeline JSON files or a single
    JSON file.  Returns ``True`` on success.
    """
    resource = _get_resource()
    if resource is None:
        raise ActionError("Resource initialization failed.")

    with Timer("pipeline load", log=_log):
        return resource.post_pipeline(str(path)).wait().succeeded


def run_pipeline(
    controller: Controller,
    entry: str,
    pipeline_override: dict[str, Any] | None = None,
) -> TaskDetail:
    """Execute a pipeline from *entry* and return the TaskDetail.

    Blocks until the pipeline finishes.  Raises :class:`ActionError` if
    the tasker cannot be initialised or if the pipeline returns no result.
    """
    tasker = _get_tasker(controller)
    if tasker is None:
        raise ActionError("Failed to initialize tasker.")

    with Timer("pipeline execution", log=_log):
        task_job = tasker.post_task(entry, pipeline_override or {})
        detail = task_job.wait().get()

    if detail is None:
        raise ActionError("Pipeline execution returned no result.")
    return detail


def list_nodes() -> list[str]:
    """Return all node names currently loaded in the Resource."""
    resource = _get_resource()
    if resource is None:
        raise ActionError("Resource not initialized.")
    return resource.node_list


def get_node_data(name: str) -> dict[str, Any] | None:
    """Return the JSON definition of a single node, or ``None``."""
    resource = _get_resource()
    if resource is None:
        return None
    return resource.get_node_data(name)


def validate_pipeline(path: str | Path) -> dict[str, Any]:
    """Validate a pipeline JSON/directory by attempting to load it.

    Returns ``{"valid": True, "nodes": [...], "node_count": N}`` on success,
    or ``{"valid": False, "error": "..."}`` on failure.
    """
    try:
        ok = load_pipeline(path)
    except ActionError as exc:
        return {"valid": False, "error": str(exc), "nodes": [], "node_count": 0}

    if not ok:
        return {"valid": False, "error": "Pipeline loading failed.", "nodes": [], "node_count": 0}

    try:
        nodes = list_nodes()
    except ActionError:
        nodes = []

    return {"valid": True, "nodes": nodes, "node_count": len(nodes)}
