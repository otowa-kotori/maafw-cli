"""Recognition service — generic reco command."""
from __future__ import annotations

from maafw_cli.core.log import Timer
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service


def _parse_kv_params(params: str | None) -> dict[str, str]:
    """Parse ``"key1=val1 key2=val2"`` into a dict.

    Returns an empty dict when *params* is ``None`` or empty.
    """
    if not params:
        return {}
    result: dict[str, str] = {}
    for token in params.split():
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


@service(name="reco")
def do_reco(
    ctx: ServiceContext,
    reco_type: str | None = None,
    params: str | None = None,
    raw: str | None = None,
) -> dict:
    """Run a recognition operation and return element references.

    Parameters
    ----------
    reco_type:
        Recognition type (``"TemplateMatch"``, ``"FeatureMatch"``,
        ``"ColorMatch"``, ``"OCR"``). Ignored when *raw* is provided.
    params:
        Space-separated ``key=value`` pairs (e.g.
        ``"template=button.png roi=0,0,400,200 threshold=0.8"``).
    raw:
        Raw JSON string (e.g.
        ``'{"recognition":"TemplateMatch","template":["b.png"]}'``).
        When provided, *reco_type* and *params* are ignored.
    """
    from maafw_cli.maafw.recognition import recognize

    parsed_params = _parse_kv_params(params) if raw is None else None

    with Timer("reco service") as t:
        resolved_type, results = recognize(
            ctx.controller,
            reco_type=reco_type or "",
            params=parsed_params,
            raw=raw,
        )

    elapsed_ms = t.elapsed_ms

    store = ctx.get_element_store()
    elements = store.build_from_results(results, resolved_type)
    store.save()

    return {
        "session": ctx.session_name or "default",
        "reco_type": resolved_type,
        "results": [e.to_dict() for e in elements],
        "elapsed_ms": elapsed_ms,
    }
