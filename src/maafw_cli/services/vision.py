"""
Vision services — OCR, screenshot.
"""
from __future__ import annotations

from typing import Optional

from maafw_cli.core.errors import ActionError, RecognitionError
from maafw_cli.core.log import Timer
from maafw_cli.core.textref import TextRefStore
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service


@service(name="ocr")
def do_ocr(ctx: ServiceContext) -> dict:
    with Timer("ocr service") as t:
        from maafw_cli.maafw.vision import ocr as _ocr

        results = _ocr(ctx.controller)

    elapsed_ms = t.elapsed_ms

    if results is None:
        from maafw_cli.download import check_ocr_files_exist

        if not check_ocr_files_exist():
            raise RecognitionError("OCR model not found. Run: maafw-cli resource download-ocr")
        raise RecognitionError("OCR failed.")

    store = TextRefStore(ctx.textrefs_path)
    refs = store.build_from_ocr(results)
    store.save()

    return {
        "session": "default",
        "results": [r.to_dict() for r in refs],
        "elapsed_ms": elapsed_ms,
    }


@service(human=lambda r: f"Saved: {r['path']}")
def do_screenshot(ctx: ServiceContext, output: Optional[str] = None) -> dict:
    from maafw_cli.maafw.vision import screencap_to_file

    path = screencap_to_file(ctx.controller, output)
    if path is None:
        raise ActionError("Screenshot failed.")
    return {"path": str(path.absolute())}
