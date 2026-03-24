"""
Vision operations — screenshot + OCR via MaaFramework.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
from maa.controller import Controller
from maa.define import OCRResult
from maa.resource import Resource
from maa.tasker import Tasker, TaskDetail
from maa.pipeline import JRecognitionType, JOCR

from maafw_cli.core.log import Timer
from maafw_cli.download import check_ocr_files_exist
from maafw_cli.paths import get_resource_dir

_log = logging.getLogger("maafw_cli.vision")

# ── cached resource ──────────────────────────────────────────────

_cached_resource: Resource | None = None


def _get_resource() -> Resource | None:
    """Return a cached Resource instance, creating one on first call.

    The Resource (OCR model bundle) is expensive to load (~200-500ms) but
    stateless — it can safely be reused across controllers and OCR calls.
    """
    global _cached_resource
    if _cached_resource is not None:
        return _cached_resource

    resource_path = get_resource_dir()
    resource = Resource()

    if not resource.use_directml():
        _log.debug("DirectML not available, falling back to CPU inference")

    with Timer("resource bundle load", log=_log):
        if not resource.post_bundle(str(resource_path)).wait().succeeded:
            return None

    _cached_resource = resource
    return resource


def _get_tasker(controller: Controller) -> Tasker | None:
    """Create a Tasker bound to *controller* with a (cached) Resource."""
    resource = _get_resource()
    if resource is None:
        return None
    tasker = Tasker()
    tasker.bind(resource, controller)
    if not tasker.inited:
        return None
    return tasker


def screencap(controller: Controller) -> Any:
    """Take a screenshot and return the raw image (numpy array).

    Returns ``None`` on failure.
    """
    with Timer("screencap", log=_log):
        return controller.post_screencap().wait().get()


def screencap_to_file(controller: Controller, output: str | Path | None = None) -> Path | None:
    """Take a screenshot and save to *output* (or an auto-named file).

    Returns the path on success, ``None`` on failure.
    """
    image = screencap(controller)
    if image is None:
        return None

    if output is None:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = Path(f"screenshot_{ts}.png")
    else:
        output = Path(output)

    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), image):
        return None
    return output


def ocr(controller: Controller, roi: tuple[int, int, int, int] | None = None) -> list[OCRResult] | None:
    """Run OCR, optionally restricted to *roi* ``(x, y, w, h)``.

    Returns a list of ``OCRResult`` (with ``.text``, ``.box``, ``.score``),
    or ``None`` on failure.
    """
    with Timer("total OCR pipeline", log=_log):
        if not check_ocr_files_exist():
            return None

        tasker = _get_tasker(controller)
        if tasker is None:
            return None

        image = screencap(controller)
        if image is None:
            return None

        ocr_params = JOCR()
        if roi is not None:
            ocr_params.roi = roi

        with Timer("OCR inference", log=_log):
            info: TaskDetail | None = (
                tasker.post_recognition(JRecognitionType.OCR, ocr_params, image).wait().get()
            )
        if not info:
            return None

        return info.nodes[0].recognition.all_results  # type: ignore[return-value]
