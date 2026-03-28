"""
Pipeline operations — load, run, list, get, validate via MaaFramework.

All functions take a ``Session`` as their first argument for
per-session resource isolation.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from maa.tasker import TaskDetail

from maafw_cli.core.errors import ActionError
from maafw_cli.core.log import Timer
from maafw_cli.core.session import Session

_log = logging.getLogger("maafw_cli.maafw.pipeline")


def load_pipeline(session: Session, path: str | Path) -> bool:
    """Load pipeline JSON/directory into the session's Resource."""
    return session.load_pipeline(str(path))


def run_pipeline(
    session: Session,
    entry: str,
    pipeline_override: dict[str, Any] | None = None,
) -> TaskDetail:
    """Execute a pipeline from *entry* and return the TaskDetail.

    Blocks until the pipeline finishes.  Raises :class:`ActionError` if
    the tasker cannot be initialised or if the pipeline returns no result.
    """
    tasker = session.get_tasker()
    if tasker is None:
        raise ActionError("Failed to initialize tasker.")

    with Timer("pipeline execution", log=_log):
        task_job = tasker.post_task(entry, pipeline_override or {})
        detail = task_job.wait().get()

    if detail is None:
        raise ActionError("Pipeline execution returned no result.")
    return detail


def list_nodes(session: Session) -> list[str]:
    """Return all node names currently loaded in the session's Resource."""
    return session.list_nodes()


def get_node_data(session: Session, name: str) -> dict[str, Any] | None:
    """Return the JSON definition of a single node, or ``None``."""
    return session.get_node_data(name)


def validate_pipeline(session: Session, path: str | Path) -> dict[str, Any]:
    """Validate a pipeline JSON/directory by attempting to load it.

    Returns ``{"valid": True, "nodes": [...], "node_count": N}`` on success,
    or ``{"valid": False, "error": "..."}`` on failure.
    """
    try:
        ok = load_pipeline(session, path)
    except ActionError as exc:
        return {"valid": False, "error": str(exc), "nodes": [], "node_count": 0}

    if not ok:
        return {"valid": False, "error": "Pipeline loading failed.", "nodes": [], "node_count": 0}

    try:
        nodes = list_nodes(session)
    except ActionError:
        nodes = []

    return {"valid": True, "nodes": nodes, "node_count": len(nodes)}
