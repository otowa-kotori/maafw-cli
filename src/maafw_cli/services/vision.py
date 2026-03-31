"""
Vision services — OCR, screenshot.
"""
from __future__ import annotations

from maafw_cli.core.errors import ActionError
from maafw_cli.core.log import Timer
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service


def _parse_roi(roi: str | None) -> tuple[int, int, int, int] | None:
    """Parse ``"x,y,w,h"`` into a tuple, or return None."""
    if roi is None:
        return None
    parts = [p.strip() for p in roi.split(",")]
    if len(parts) != 4:
        raise ActionError(f"Invalid ROI '{roi}'. Expected format: x,y,w,h")
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise ActionError(f"Invalid ROI '{roi}'. All values must be integers.")


@service(name="ocr")
def do_ocr(ctx: ServiceContext, roi: str | None = None) -> dict:
    with Timer("ocr service") as t:
        from maafw_cli.maafw.vision import ocr as _ocr

        roi_tuple = _parse_roi(roi)
        results, screenshot_path = _ocr(ctx.session, roi=roi_tuple)

    elapsed_ms = t.elapsed_ms

    store = ctx.get_element_store()
    elements = store.build_from_ocr(results)

    result = {
        "session": ctx.session_name,
        "results": [e.to_dict() for e in elements],
        "elapsed_ms": elapsed_ms,
    }
    if screenshot_path is not None:
        result["screenshot"] = str(screenshot_path)
    return result


@service(human=lambda r: f"Saved: {r['path']}")
def do_screenshot(ctx: ServiceContext, output: str | None = None) -> dict:
    from maafw_cli.maafw.vision import screencap_to_file

    path = screencap_to_file(ctx.controller, output)
    if path is None:
        raise ActionError("Screenshot failed.")
    return {"path": str(path.absolute())}
