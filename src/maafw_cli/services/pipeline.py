"""
Pipeline services — run, load, list, show, validate.

``pipeline_run`` needs a session (controller) to execute pipelines.
All other services are ``needs_session=False`` — they only operate on
the global cached Resource.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from maafw_cli.core.errors import ActionError
from maafw_cli.core.log import Timer
from maafw_cli.maafw import init_toolkit
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service

_log = logging.getLogger("maafw_cli.services.pipeline")


# ── helpers ──────────────────────────────────────────────────────


def _summarize_node(nd: Any) -> dict[str, Any]:
    """Extract a JSON-serializable summary from a NodeDetail."""
    result: dict[str, Any] = {"name": nd.name, "completed": nd.completed}

    if nd.recognition:
        reco = nd.recognition
        reco_info: dict[str, Any] = {
            "algorithm": str(reco.algorithm),
            "hit": reco.hit,
        }
        if reco.box:
            reco_info["box"] = list(reco.box)
        # best_result may carry score / text depending on algorithm
        if reco.best_result:
            br = reco.best_result
            if hasattr(br, "score") and br.score is not None:
                reco_info["score"] = br.score
            if hasattr(br, "text") and br.text is not None:
                reco_info["text"] = br.text
        result["recognition"] = reco_info

    if nd.action:
        result["action"] = {
            "type": str(nd.action.action),
            "success": nd.action.success,
        }

    return result


def _human_run(r: dict) -> str:
    """Default one-line summary for pipeline run."""
    entry = r.get("entry", "?")
    session = r.get("session", "default")
    status = r.get("status", "unknown")
    count = r.get("node_count", 0)
    elapsed = r.get("elapsed_ms", 0)
    return f"Pipeline: {entry} \u2014 {session}\nStatus: {status} | {count} nodes | {elapsed}ms"


# ── services ─────────────────────────────────────────────────────


@service(name="pipeline_run", human=_human_run)
def do_pipeline_run(
    ctx: ServiceContext,
    path: str,
    entry: str | None = None,
    override: str | None = None,
) -> dict:
    """Load a pipeline and execute it from *entry*.

    If *entry* is ``None``, defaults to the first loaded node.
    *override* is a JSON string of per-node overrides.
    """
    from maafw_cli.maafw.pipeline import load_pipeline, run_pipeline, list_nodes

    init_toolkit()

    # 1. Load pipeline definitions
    ok = load_pipeline(path)
    if not ok:
        raise ActionError(f"Failed to load pipeline from: {path}")

    # 2. Resolve entry
    if entry is None:
        nodes = list_nodes()
        if not nodes:
            raise ActionError("Pipeline loaded but contains no nodes.")
        entry = nodes[0]

    # 3. Parse override JSON
    override_dict: dict[str, Any] | None = None
    if override is not None:
        try:
            override_dict = json.loads(override)
        except json.JSONDecodeError as exc:
            raise ActionError(f"Invalid override JSON: {exc}")

    # 4. Execute
    with Timer("pipeline_run service", log=_log) as t:
        detail = run_pipeline(ctx.controller, entry, override_dict)

    # 5. Summarise
    node_summaries = [_summarize_node(nd) for nd in detail.nodes] if detail.nodes else []

    status = "succeeded" if detail.nodes else "no_nodes"

    return {
        "session": ctx.session_name or "default",
        "entry": entry,
        "status": status,
        "nodes": node_summaries,
        "node_count": len(node_summaries),
        "elapsed_ms": t.elapsed_ms,
    }


@service(
    name="pipeline_load",
    needs_session=False,
    human=lambda r: f"Loaded {r['node_count']} nodes from pipeline.",
)
def do_pipeline_load(path: str) -> dict:
    """Load pipeline definitions into the Resource (without executing)."""
    from maafw_cli.maafw.pipeline import load_pipeline, list_nodes

    init_toolkit()
    ok = load_pipeline(path)
    if not ok:
        raise ActionError(f"Failed to load pipeline from: {path}")

    nodes = list_nodes()
    return {"loaded": True, "nodes": nodes, "node_count": len(nodes)}


@service(
    name="pipeline_list",
    needs_session=False,
    human=lambda r: "\n".join(r["nodes"]) if r["nodes"] else "(no nodes loaded)",
)
def do_pipeline_list() -> dict:
    """List all node names currently loaded in the Resource."""
    from maafw_cli.maafw.pipeline import list_nodes

    nodes = list_nodes()
    return {"nodes": nodes, "node_count": len(nodes)}


@service(name="pipeline_show", needs_session=False)
def do_pipeline_show(node: str) -> dict:
    """Return the full JSON definition of a single node."""
    from maafw_cli.maafw.pipeline import get_node_data

    definition = get_node_data(node)
    if definition is None:
        raise ActionError(f"Node not found: {node}")
    return {"node": node, "definition": definition}


@service(name="pipeline_validate", needs_session=False)
def do_pipeline_validate(path: str) -> dict:
    """Validate a pipeline JSON/directory by attempting to load it."""
    from maafw_cli.maafw.pipeline import validate_pipeline

    init_toolkit()
    return validate_pipeline(path)
