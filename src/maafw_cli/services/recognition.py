"""Recognition service — generic reco command."""
from __future__ import annotations

from maafw_cli.core.log import Timer
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service


def _parse_kv_params(params: str | list[str] | tuple[str, ...] | None) -> dict[str, str]:
    """Parse ``key=value`` tokens into a dict.

    Accepts either a legacy space-separated string or the original CLI token
    list/tuple, preserving embedded spaces inside a single argument.
    Returns an empty dict when *params* is ``None`` or empty.
    """
    if not params:
        return {}

    tokens = params.split() if isinstance(params, str) else params
    result: dict[str, str] = {}
    for token in tokens:
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
    params: str | list[str] | tuple[str, ...] | None = None,
    raw: str | None = None,
) -> dict:
    """Run a recognition operation and return element references.

    Parameters
    ----------
    reco_type:
        Recognition type (``"TemplateMatch"``, ``"FeatureMatch"``,
        ``"ColorMatch"``, ``"OCR"``). Ignored when *raw* is provided.
    params:
        ``key=value`` 参数。既支持旧的空格分隔字符串（例如
        ``"template=button.png roi=0,0,400,200 threshold=0.8"``），
        也支持命令层直接传下来的参数 token 列表，以保留单个参数中的空格。
    raw:
        Raw JSON string (e.g.
        ``'{"recognition":"TemplateMatch","template":["b.png"]}'``).
        When provided, *reco_type* and *params* are ignored.
    """
    from maafw_cli.maafw.recognition import recognize

    parsed_params = _parse_kv_params(params) if raw is None else None

    with Timer("reco service") as t:
        resolved_type, results, screenshot_path = recognize(
            ctx.session,
            reco_type=reco_type or "",
            params=parsed_params,
            raw=raw,
        )

    elapsed_ms = t.elapsed_ms

    store = ctx.get_element_store()
    elements = store.build_from_results(results, resolved_type)

    result = {
        "session": ctx.session_name,
        "reco_type": resolved_type,
        "results": [e.to_dict() for e in elements],
        "elapsed_ms": elapsed_ms,
    }
    if screenshot_path is not None:
        result["screenshot"] = str(screenshot_path)
    return result
